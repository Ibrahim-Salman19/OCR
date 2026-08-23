import pytest
from PIL import Image, ImageDraw
from unittest.mock import MagicMock, patch
from tests.e2e.conftest import mock_redis, patch_redis


@pytest.fixture
def temp_workspace(tmp_path):
    """Create isolated workspace"""
    workspace = {
        "input": tmp_path / "input",
        "output": tmp_path / "output",
        "db": tmp_path / "test.db",
        "logs": tmp_path / "logs",
    }
    for p in workspace.values():
        if p.suffix:  # file
            pass
        else:
            p.mkdir()
    return workspace


@pytest.fixture
def sample_image(temp_workspace):
    """Create a test image with known text"""
    img_path = temp_workspace["input"] / "test_page.png"

    img = Image.new("RGB", (800, 200), color="white")
    draw = ImageDraw.Draw(img)
    # Use default font
    draw.text((10, 50), "Sample OCR Test Text", fill="black")

    img.save(img_path)
    return str(img_path)


@pytest.fixture(autouse=True)
def mock_env(monkeypatch, temp_workspace):
    """Set environment variables for testing"""
    monkeypatch.setenv("BLAST_OCR_DATABASE_URL", f"sqlite:///{temp_workspace['db']}")
    monkeypatch.setenv("BLAST_OCR_LOG_DIR", str(temp_workspace["logs"]))
    monkeypatch.setenv("BLAST_OCR_OCR_GPU", "false")


@pytest.fixture(autouse=True)
def mock_easyocr_reader_for_tests(request):
    """Mock EasyOCR reader by default to prevent C-level crashes in tests.

    Opt-out with @pytest.mark.real_easyocr for tests that explicitly need real engine behavior.
    """
    if request.node.get_closest_marker("real_easyocr"):
        yield
        return

    with patch("easyocr.Reader") as mock_reader_cls:
        mock_reader = MagicMock()
        mock_reader.readtext.return_value = [
            (
                [[0, 0], [20, 0], [20, 10], [0, 10]],
                "mocked text",
                0.95,
            )
        ]
        mock_reader_cls.return_value = mock_reader
        yield


@pytest.fixture(autouse=True)
def auto_patch_redis(request, mock_redis):
    """Autouse patch for queue client to use isolated mock_redis in tests except test_queue.py."""
    if request.node.fspath and "test_queue.py" in str(request.node.fspath):
        yield
        return
    try:
        import redis  # noqa: F401
        has_redis = True
    except ImportError:
        has_redis = False

    if has_redis:
        with patch("blast_ocr.queue.client.get_redis_connection", return_value=mock_redis), \
             patch("redis.Redis.from_url", return_value=mock_redis), \
             patch("redis.from_url", return_value=mock_redis):
            yield mock_redis
    else:
        with patch("blast_ocr.queue.client.get_redis_connection", return_value=mock_redis):
            yield mock_redis
