"""
blast_ocr.integrations.llamaindex_reader

Native Reader for LlamaIndex.
Enables ingestion of PDF, images, and presentations via B.L.A.S.T. OCR into LlamaIndex indices.
"""

from typing import List, Optional, Dict, Any, Union
from pathlib import Path

from blast_ocr.pipeline import BlastPipeline


class BlastOCRReader:
    """
    LlamaIndex-compatible BaseReader powered by B.L.A.S.T. OCR Engine.
    
    Usage:
        reader = BlastOCRReader(engine="rapidocr")
        documents = reader.load_data("report.pdf")
        index = VectorStoreIndex.from_documents(documents)
    """

    def __init__(
        self,
        engine: str = "rapidocr",
        secure_mode: bool = False,
        enable_book_intelligence: bool = True,
        enable_tier0_routing: bool = True,
        config_overrides: Optional[Dict[str, Any]] = None,
    ):
        self.engine = engine
        self.secure_mode = secure_mode
        self.enable_book_intelligence = enable_book_intelligence
        self.enable_tier0_routing = enable_tier0_routing

        overrides = {
            "ocr_engine": engine,
            "secure_mode": secure_mode,
            "enable_book_intelligence": enable_book_intelligence,
            "enable_tier0_routing": enable_tier0_routing,
        }
        if config_overrides:
            overrides.update(config_overrides)
        self.config_overrides = overrides

    def load_data(
        self,
        file_path: Union[str, Path],
        extra_info: Optional[Dict[str, Any]] = None,
    ) -> List[Any]:
        """
        Processes the input file and returns a list of LlamaIndex Document objects.
        """
        fpath = str(Path(file_path).resolve())
        pipeline = BlastPipeline(config_overrides=self.config_overrides)
        try:
            result = pipeline.process_job(fpath)
        finally:
            pipeline.close()

        # Try importing LlamaIndex Document
        try:
            from llama_index.core.schema import Document as LlamaDocument
        except ImportError:
            try:
                from llama_index.schema import Document as LlamaDocument
            except ImportError:
                class LlamaDocument:  # Fallback lightweight schema
                    def __init__(self, text: str, extra_info: Optional[Dict[str, Any]] = None):
                        self.text = text
                        self.extra_info = extra_info or {}

                    def __repr__(self):
                        return f"Document(text={self.text[:50]!r}..., extra_info={self.extra_info})"

        output_files = result.get("output_files", {})
        md_file = output_files.get("md")
        full_text = ""
        if md_file and Path(md_file).exists():
            full_text = Path(md_file).read_text(encoding="utf-8", errors="ignore")

        metadata = {
            "file_path": fpath,
            "file_name": Path(fpath).name,
            "pages_processed": result.get("pages_processed", 1),
            "engine": self.engine,
            "secure_mode": self.secure_mode,
            "generated_files": result.get("generated_files", {}),
        }
        if extra_info:
            metadata.update(extra_info)

        doc = LlamaDocument(text=full_text, extra_info=metadata)
        return [doc]
