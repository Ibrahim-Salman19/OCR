"""
blast_ocr.integrations.langchain_loader

Native Document Loader for LangChain.
Enables seamless loading of PDFs, scanned books, and images via B.L.A.S.T. OCR.
"""

from typing import List, Optional, Dict, Any, Union
from pathlib import Path

from blast_ocr.pipeline import BlastPipeline

try:
    from langchain_core.documents import Document as LCDocument
except ImportError:
    try:
        from langchain.docstore.document import Document as LCDocument
    except ImportError:
        class LCDocument:  # type: ignore[no-redef]
            def __init__(self, page_content: str, metadata: Dict[str, Any]):
                self.page_content = page_content
                self.metadata = metadata

            def __repr__(self):
                return f"Document(page_content={self.page_content[:50]!r}..., metadata={self.metadata})"


class BlastOCRDocumentLoader:
    """
    LangChain-compatible Document Loader powered by B.L.A.S.T. OCR Engine.
    
    Usage:
        loader = BlastOCRDocumentLoader("my_book.pdf", engine="rapidocr", secure_mode=True)
        docs = loader.load()
        for doc in docs:
            print(doc.page_content, doc.metadata)
    """

    def __init__(
        self,
        file_path: Union[str, Path],
        engine: str = "rapidocr",
        secure_mode: bool = False,
        enable_book_intelligence: bool = True,
        enable_tier0_routing: bool = True,
        config_overrides: Optional[Dict[str, Any]] = None,
    ):
        self.file_path = str(Path(file_path).resolve())
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

    def lazy_load(self):
        """
        Lazily yields LangChain Document objects.
        """
        pipeline = BlastPipeline(config_overrides=self.config_overrides)
        try:
            result = pipeline.process_job(self.file_path)
        finally:
            pipeline.close()

        source_name = Path(self.file_path).name

        output_files = result.get("output_files", {})
        md_file = output_files.get("md")
        full_text = result.get("text") or result.get("full_text") or ""
        if not full_text and md_file and Path(md_file).exists():
            full_text = Path(md_file).read_text(encoding="utf-8", errors="ignore")

        metadata = {
            "source": self.file_path,
            "filename": source_name,
            "pages_processed": result.get("pages_processed", 1),
            "engine": self.engine,
            "secure_mode": self.secure_mode,
            "generated_files": result.get("generated_files", {}),
        }

        yield LCDocument(page_content=full_text, metadata=metadata)

    def load(self) -> List[Any]:
        """
        Executes OCR extraction and returns a list of LangChain Document objects.
        """
        return list(self.lazy_load())
