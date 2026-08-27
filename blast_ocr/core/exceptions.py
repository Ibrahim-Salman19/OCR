class BLASTOCRException(Exception):
    """Base exception for all BLAST OCR errors"""

    pass


class ImageLoadError(BLASTOCRException):
    """Failed to load or decode image"""

    pass


class OCREngineError(BLASTOCRException):
    """OCR engine initialization or processing failed"""

    pass


class PageExtractionError(BLASTOCRException):
    """Failed to extract text from page"""

    def __init__(self, page_number, original_error):
        self.page_number = page_number
        self.original_error = original_error
        super().__init__(f"Page {page_number} extraction failed: {original_error}")


class LowConfidenceError(BLASTOCRException):
    """OCR confidence below threshold"""

    def __init__(self, confidence, threshold):
        self.confidence = confidence
        self.threshold = threshold
        super().__init__(f"Confidence {confidence:.2f} < {threshold:.2f}")


class OutputWriteError(BLASTOCRException):
    """Failed to write results to disk"""

    pass


class OCREngineInitializationError(OCREngineError):
    """OCR engine backend failed to initialize or load weights"""

    pass


class CorruptedDocumentError(BLASTOCRException):
    """Failed to parse or rasterize corrupted document"""

    pass
