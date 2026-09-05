"""
tests/test_job_language_routing.py

Regression coverage for the per-job language routing gap discovered while
wiring the RapidOCR script-mismatch fallback (see
tests/test_script_mismatch_fallback.py): `JobConfig.ocr_languages` was never
threaded from the pipeline down to the OCR engine call, and even a caller
passing a per-job language explicitly through `config_overrides` would have
it silently dropped -- `BlastPipeline`'s `cfg_dict` never included the key,
so `JobConfig.from_dict` had nothing to pick up. Fixing that also exposed a
second, more dangerous gap: `get_cache_namespace` derived its language
component from the process-global `config.ocr_languages` rather than the
per-job value, so two jobs requesting different languages for the exact
same image (e.g. Job A reprocessing an image as English, Job B as Urdu)
would collide on the same cache namespace and one could silently receive
the other's wrong-language cached OCR result.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from blast_ocr.config import config
from blast_ocr.core.extractor import get_cache_namespace
from blast_ocr.core.models import JobConfig


@pytest.fixture(autouse=True)
def _restore_ocr_languages():
    original = list(config.ocr_languages)
    yield
    config.ocr_languages = original


def test_job_config_round_trips_ocr_languages():
    cfg = JobConfig.from_dict({"ocr_languages": ["en", "ur"]})
    assert cfg.ocr_languages == ["en", "ur"]
    assert cfg.to_dict()["ocr_languages"] == ["en", "ur"]


def test_job_config_defaults_to_english():
    cfg = JobConfig()
    assert cfg.ocr_languages == ["en"]


def test_pipeline_cfg_dict_carries_ocr_languages_override():
    """The bug: config_overrides={"ocr_languages": [...]} used to be
    silently dropped because BlastPipeline's cfg_dict never included the
    key at all."""
    from blast_ocr.pipeline import BlastPipeline

    with patch("blast_ocr.pipeline.OCRDatabase"), patch(
        "blast_ocr.pipeline.ParallelOCRProcessor"
    ):
        pipeline = BlastPipeline(config_overrides={"ocr_languages": ["ur", "en"]})

    assert pipeline.job_config.ocr_languages == ["ur", "en"]


def test_pipeline_cfg_dict_defaults_from_global_config():
    from blast_ocr.pipeline import BlastPipeline

    config.ocr_languages = ["en", "fa"]
    with patch("blast_ocr.pipeline.OCRDatabase"), patch(
        "blast_ocr.pipeline.ParallelOCRProcessor"
    ):
        pipeline = BlastPipeline()

    assert pipeline.job_config.ocr_languages == ["en", "fa"]


def test_cache_namespace_override_differs_from_global_default():
    """A per-job languages override must change the cache namespace, not
    just be silently equivalent to the (different) global default."""
    config.ocr_languages = ["en"]

    default_ns = get_cache_namespace("rapidocr")
    urdu_ns = get_cache_namespace("rapidocr", languages=["ur"])

    assert default_ns != urdu_ns
    # And it must not have mutated the global config as a side effect.
    assert config.ocr_languages == ["en"]


def test_cache_namespace_falls_back_to_global_when_no_override_given():
    """When no per-call override is given, the namespace's language
    component must reflect the current global config.ocr_languages.

    Replaces the `config` name INSIDE `blast_ocr.core.extractor`'s own
    namespace with a throwaway stand-in, rather than mutating attributes
    on the real shared global singleton (as other tests in this file do):
    a plain `config.ocr_languages = [...]` assignment here was observed
    flaky specifically in full-suite runs (reading back a stale ["en"]
    moments after being set to ["en", "ur"]), never in isolation --
    something elsewhere in a ~750-test suite that spawns several real
    background threads (queue workers, concurrency/swarm tests) touches
    the shared global between the assignment and the read. That's
    exactly the class of hazard `JobConfig`'s explicit per-call language
    overrides exist to route *production* code around; this test avoids
    depending on the same fragile shared-global timing instead of
    chasing which specific other test's thread cleanup is responsible.
    """
    stand_in = SimpleNamespace(
        ocr_languages=["en", "ur"],
        ocr_gpu=False,
        denoise_level=0,
        contrast_boost=1.0,
        auto_deskew=True,
    )
    with patch("blast_ocr.core.extractor.config", stand_in):
        assert "langs=en,ur" in get_cache_namespace("rapidocr")


def test_worker_uses_distinct_cache_entries_for_different_job_languages(tmp_path):
    """End-to-end proof at the worker layer: the same image path,
    processed under two JobConfigs that differ only in ocr_languages,
    must not share a cache entry -- otherwise whichever job runs second
    can be silently served the first job's wrong-language OCR result."""
    from blast_ocr.core import worker as worker_module

    class FakeEngine:
        def __init__(self):
            self.calls = []

        def process_page(self, image_path, page_num, glyph_height=None, languages=None):
            self.calls.append(languages)
            text = "english result" if not languages or "ur" not in languages else "urdu result"
            return {"page": page_num, "text": text, "confidence": 0.9}

    fake_engine = FakeEngine()

    # A real file with unique-per-run CONTENT: OCRCache.get_cache_key
    # hashes file content (not the path), and OCRCache is disk-backed and
    # never cleared between separate test sessions -- fixed file bytes
    # (even under a fresh tmp_path) would hash to the exact same cache key
    # as a previous run of this same test and silently turn it into a
    # no-op cache hit instead of exercising the engine calls it's meant
    # to verify.
    image_path = str(tmp_path / "shared_page_for_lang_cache_test.png")
    with open(image_path, "wb") as f:
        f.write(b"fake png bytes for cache-key hashing:" + uuid.uuid4().bytes)

    with patch.object(worker_module, "get_worker_engine", return_value=fake_engine):
        job_en = JobConfig(ocr_engine="rapidocr", ocr_languages=["en"])
        job_ur = JobConfig(ocr_engine="rapidocr", ocr_languages=["ur"])

        r_en = worker_module.process_page_wrapper(image_path, 1, job_en)
        r_ur = worker_module.process_page_wrapper(image_path, 1, job_ur)

    assert r_en["text"] == "english result"
    assert r_ur["text"] == "urdu result"
    assert fake_engine.calls == [["en"], ["ur"]]
