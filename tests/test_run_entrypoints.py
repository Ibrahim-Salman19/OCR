import importlib


def test_streamlit_app_importable():
    module = importlib.import_module("streamlit_app")
    assert hasattr(module, "main")


def test_run_module_importable():
    module = importlib.import_module("run")
    assert hasattr(module, "main")
