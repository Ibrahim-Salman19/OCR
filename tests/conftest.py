import pytest
from PIL import Image, ImageDraw


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
    monkeypatch.setenv("BLAST_OCR_KEY_LOG_DIR", str(temp_workspace["logs"]))
    monkeypatch.setenv("BLAST_OCR_OCR_GPU", "false")
