import importlib


def test_streamlit_app_module_imports_run_gui_main():
    module = importlib.import_module("streamlit_app")
    assert hasattr(module, "main")
