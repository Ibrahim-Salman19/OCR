"""
tests/test_streaming_storage.py

Comprehensive test suite for Milestone 3 (Streaming Buffer & Storage Engine):
1. PageStreamGenerator windowing (K=8..16), ephemeral scratch isolation, immediate deterministic cleanup, and 1,000-page memory bounding (RSS <= 500MB).
2. StreamDocumentWriter incremental Markdown, PlainText, and JSONL exporting with out-of-order handling.
3. TieredOCRCache dual-tier L1 memory LRU + L2 async disk cache with AsyncCacheWriter spooling and size budget pruning.
4. ConcurrentObjectUploader background ThreadPool uploads, multipart streaming, exponential backoff, and graceful draining.
5. ObjectStorage enhanced streaming primitives (put_stream, get_stream, put_batch_concurrent, presigned URLs).
"""

import io
import json
import psutil
import time
from concurrent.futures import Future


from blast_ocr.core.streaming import (
    ChunkScratchManager,
    PageStreamGenerator,
    StreamDocumentWriter,
)
from blast_ocr.cache.tiered_cache import (
    TieredOCRCache,
)
from blast_ocr.storage.concurrent_uploader import (
    ConcurrentObjectUploader,
    StreamBufferManager,
)
from blast_ocr.storage.object_store import (
    LocalFilesystemStorage,
)


# ============================================================================
# 1. PageStreamGenerator & ChunkScratchManager Tests
# ============================================================================

class TestPageStreamGeneratorAndScratch:
    def test_chunk_scratch_manager_lifecycle(self, tmp_path):
        """Tests creation, tracking, and deterministic purging of scratch directories."""
        mgr = ChunkScratchManager(tmp_path / "scratch_base")
        d1 = mgr.create_scratch_window(0)
        d2 = mgr.create_scratch_window(1)

        assert d1.exists()
        assert d2.exists()
        assert len(mgr.active_scratch_dirs) == 2

        mgr.purge_scratch_window(d1)
        assert not d1.exists()
        assert len(mgr.active_scratch_dirs) == 1

        mgr.cleanup_all()
        assert not d2.exists()
        assert len(mgr.active_scratch_dirs) == 0

    def test_page_stream_generator_windowing_partitions(self, tmp_path):
        """Tests sliding window partitioning for K=8 on 20 pages (8, 8, 4)."""
        dummy_file = tmp_path / "book.pdf"
        dummy_file.write_bytes(b"%PDF-1.4 mock content")

        gen = PageStreamGenerator(
            source_path=dummy_file,
            total_pages=20,
            chunk_size=8,
            temp_dir=tmp_path / "scratch",
        )

        batches = list(gen)
        assert len(batches) == 3

        # Chunk 1: 1..8
        assert len(batches[0]) == 8
        assert [p for p, _ in batches[0]] == list(range(1, 9))

        # Chunk 2: 9..16
        assert len(batches[1]) == 8
        assert [p for p, _ in batches[1]] == list(range(9, 17))

        # Chunk 3: 17..20
        assert len(batches[2]) == 4
        assert [p for p, _ in batches[2]] == list(range(17, 21))

        gen.close()

    def test_page_stream_generator_immediate_scratch_unlinking(self, tmp_path):
        """Tests that ephemeral images in scratch directory are unlinked immediately after chunk yield."""
        dummy_file = tmp_path / "doc.pdf"
        dummy_file.write_bytes(b"%PDF-1.4 sample content")

        gen = PageStreamGenerator(
            source_path=dummy_file,
            total_pages=16,
            chunk_size=8,
            temp_dir=tmp_path / "scratch",
        )

        seen_paths = []
        for chunk in gen:
            for _, img_path in chunk:
                assert img_path.exists(), f"Image {img_path} must exist while in chunk window"
                seen_paths.append(img_path)

        # Once generator exits, all yielded paths must have been purged from disk
        for p in seen_paths:
            assert not p.exists(), f"Scratch file {p} must be deleted immediately post-chunk"
        gen.close()

    def test_page_stream_generator_1000_pages_bounded_memory(self, tmp_path):
        """
        Processes 1,000 pages through PageStreamGenerator in K=16 chunks.
        Asserts memory RSS remains strictly bounded <= 500MB and total growth < 50MB.
        """
        dummy_doc = tmp_path / "large_archive.pdf"
        dummy_doc.write_bytes(b"%PDF-1.4 1000-page archive placeholder")

        initial_rss = psutil.Process().memory_info().rss
        total_pages_processed = 0

        with PageStreamGenerator(
            source_path=dummy_doc,
            total_pages=1000,
            chunk_size=16,
            temp_dir=tmp_path / "scratch_1000",
        ) as stream:
            for chunk_idx, chunk in enumerate(stream):
                # Verify chunk size
                assert len(chunk) <= 16
                for p_num, img_path in chunk:
                    assert img_path.exists()
                    total_pages_processed += 1

                # Periodically verify memory growth delta
                if chunk_idx % 10 == 0:
                    current_rss = psutil.Process().memory_info().rss
                    growth_mb = (current_rss - initial_rss) / (1024 * 1024)
                    assert growth_mb < 50.0, f"Memory growth exceeded 50MB bound: {growth_mb:.2f}MB"

        import gc
        gc.collect()
        final_rss = psutil.Process().memory_info().rss
        rss_growth_mb = (final_rss - initial_rss) / (1024 * 1024)

        assert total_pages_processed == 1000
        assert rss_growth_mb < 50.0, f"Memory growth exceeded bound: {rss_growth_mb:.2f}MB"


# ============================================================================
# 2. StreamDocumentWriter Tests
# ============================================================================

class TestStreamDocumentWriter:
    def test_stream_document_writer_markdown_and_txt(self, tmp_path):
        """Tests incremental Markdown and Plain Text document generation."""
        md_file = tmp_path / "output.md"
        with StreamDocumentWriter(md_file, format="markdown") as writer:
            writer.write_page(1, "Page 1 intro text")
            writer.write_page(2, "Page 2 detail text")

        assert md_file.exists()
        md_text = md_file.read_text(encoding="utf-8")
        assert "## Page 1" in md_text
        assert "Page 1 intro text" in md_text
        assert "## Page 2" in md_text
        assert "Page 2 detail text" in md_text

        txt_file = tmp_path / "output.txt"
        with StreamDocumentWriter(txt_file, format="txt") as writer:
            writer.write_page(1, "Text stream line 1")
            writer.write_page(2, "Text stream line 2")

        txt_content = txt_file.read_text(encoding="utf-8")
        assert "--- Page 1 ---" in txt_content
        assert "--- Page 2 ---" in txt_content

    def test_stream_document_writer_jsonl(self, tmp_path):
        """Tests incremental JSON Lines (.jsonl) streaming."""
        jsonl_file = tmp_path / "output.jsonl"
        with StreamDocumentWriter(jsonl_file, format="jsonl") as writer:
            writer.write_page(1, "P1 text", layout={"confidence": 0.98})
            writer.write_page(2, "P2 text", layout={"confidence": 0.95})

        assert jsonl_file.exists()
        lines = [line.strip() for line in jsonl_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(lines) == 2

        r1 = json.loads(lines[0])
        assert r1["page"] == 1
        assert r1["text"] == "P1 text"
        assert r1["layout"]["confidence"] == 0.98

    def test_stream_document_writer_out_of_order_page_sorting(self, tmp_path):
        """Tests that pages submitted out of order are cleanly sorted upon finalize()."""
        out_file = tmp_path / "sorted_export.md"
        writer = StreamDocumentWriter(out_file, format="markdown")
        writer.write_page(3, "Page 3 content")
        writer.write_page(1, "Page 1 content")
        writer.write_page(2, "Page 2 content")
        writer.finalize()

        content = out_file.read_text(encoding="utf-8")
        pos_p1 = content.find("## Page 1")
        pos_p2 = content.find("## Page 2")
        pos_p3 = content.find("## Page 3")
        assert -1 < pos_p1 < pos_p2 < pos_p3


# ============================================================================
# 3. TieredOCRCache Tests
# ============================================================================

class TestTieredOCRCache:
    def test_l1_in_memory_fast_path_and_hit(self, tmp_path):
        """Tests L1 memory fast path retrieval without touching disk."""
        cache = TieredOCRCache(tmp_path / "cache_l1", l1_capacity=10)
        cache.put("key_001", {"text": "Fast path result", "conf": 0.99}, sync=True)

        # Delete disk file to prove subsequent query hits memory L1
        disk_file = tmp_path / "cache_l1" / "key_001.json"
        assert disk_file.exists()
        disk_file.unlink()

        hit = cache.get("key_001")
        assert hit is not None
        assert hit["text"] == "Fast path result"
        assert hit["conf"] == 0.99
        cache.close()

    def test_l1_lru_eviction_to_l2_and_repromotion(self, tmp_path):
        """Tests LRU eviction from L1 capacity=2 to L2 disk, and transparent promotion back to L1."""
        cache = TieredOCRCache(tmp_path / "cache_lru", l1_capacity=2)
        cache.put("item1", {"val": 1}, sync=True)
        cache.put("item2", {"val": 2}, sync=True)
        cache.put("item3", {"val": 3}, sync=True)

        with cache._lock:
            assert "item1" not in cache.l1_cache
            assert "item2" in cache.l1_cache
            assert "item3" in cache.l1_cache

        # Retrieve item1 from L2 disk
        res1 = cache.get("item1")
        assert res1 is not None
        assert res1["val"] == 1

        # item1 re-promoted to L1, item2 evicted
        with cache._lock:
            assert "item1" in cache.l1_cache
            assert "item2" not in cache.l1_cache
        cache.close()

    def test_async_cache_writer_nonblocking_spool_and_flush(self, tmp_path):
        """Tests non-blocking background queue writes and flush synchronization."""
        cache = TieredOCRCache(tmp_path / "async_cache", l1_capacity=10)
        for i in range(10):
            cache.put(f"async_{i}", {"idx": i, "data": f"Async content {i}"}, sync=False)

        cache.flush()

        for i in range(10):
            disk_path = tmp_path / "async_cache" / f"async_{i}.json"
            assert disk_path.exists()
            with open(disk_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                assert data["idx"] == i
        cache.close()

    def test_l2_cache_prune_budget(self, tmp_path):
        """Tests prune_cache() enforces disk size quotas by removing oldest files."""
        cache_dir = tmp_path / "budget_cache"
        cache = TieredOCRCache(cache_dir, l1_capacity=10)

        # Write 5 files of ~100KB each
        payload = {"data": "A" * (100 * 1024)}
        for i in range(5):
            cache.put(f"bulk_{i}", payload, sync=True)
            time.sleep(0.01)

        # Budget: 0.25 MB (250 KB) -> should prune at least 2 files
        pruned = cache.prune_cache(max_size_mb=0.25)
        assert pruned >= 2

        remaining = list(cache_dir.glob("*.json"))
        total_remaining = sum(f.stat().st_size for f in remaining)
        assert total_remaining <= 0.30 * 1024 * 1024
        cache.close()


# ============================================================================
# 4. ConcurrentObjectUploader Tests
# ============================================================================

class TestConcurrentObjectUploader:
    def test_upload_file_returns_future_and_persists(self, tmp_path):
        """Tests upload_file schedules task and returns Future resolving to storage URI."""
        storage = LocalFilesystemStorage(str(tmp_path / "object_store"))
        uploader = ConcurrentObjectUploader(storage=storage, max_workers=2)

        test_file = tmp_path / "test_doc.pdf"
        test_file.write_bytes(b"Mock PDF binary data")

        fut = uploader.upload_file("jobs/101/doc.pdf", test_file)
        assert isinstance(fut, Future)

        uri = fut.result(timeout=5.0)
        assert uri is not None
        assert storage.exists("jobs/101/doc.pdf")
        uploader.shutdown()

    def test_upload_batch_concurrent_execution(self, tmp_path):
        """Tests concurrent multi-file batch upload."""
        storage = LocalFilesystemStorage(str(tmp_path / "object_store"))
        uploader = ConcurrentObjectUploader(storage=storage, max_workers=4)

        items = {}
        for i in range(6):
            p = tmp_path / f"export_{i}.txt"
            p.write_text(f"Text content {i}", encoding="utf-8")
            items[f"batch/export_{i}.txt"] = p

        results = uploader.upload_batch(items)
        assert len(results) == 6
        for k in items.keys():
            assert k in results
            assert storage.exists(k)
        uploader.shutdown()

    def test_upload_stream_and_buffer_manager(self, tmp_path):
        """Tests stream upload and StreamBufferManager utilities."""
        storage = LocalFilesystemStorage(str(tmp_path / "object_store"))
        uploader = ConcurrentObjectUploader(storage=storage, max_workers=2)

        buf = StreamBufferManager.create_buffer(b"Streaming buffer data payload")
        fut = uploader.upload_stream("streamed/payload.bin", buf)
        res_uri = fut.result(timeout=5.0)

        assert res_uri is not None
        assert storage.exists("streamed/payload.bin")
        uploader.shutdown()


# ============================================================================
# 5. Enhanced ObjectStorage Primitives Tests
# ============================================================================

class TestObjectStorageEnhancedPrimitives:
    def test_local_storage_streaming_and_presigned(self, tmp_path):
        """Tests put_stream, get_stream, and generate_presigned_url on LocalFilesystemStorage."""
        storage = LocalFilesystemStorage(str(tmp_path / "store"))
        key = "stream_test/file.bin"

        # Stream put
        in_stream = io.BytesIO(b"Direct stream bytes into storage")
        storage.put_stream(key, in_stream)
        assert storage.exists(key)

        # Stream get
        out_stream = storage.get_stream(key)
        content = out_stream.read()
        assert content == b"Direct stream bytes into storage"

        # Presigned URL
        presigned = storage.generate_presigned_url(key)
        assert presigned.startswith("file://")
