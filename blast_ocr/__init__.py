# B.L.A.S.T. OCR Package
import defusedxml
defusedxml.defuse_stdlib()

# Global security for potentially vulnerable libraries
try:
    from lxml import etree
    # Create a safe parser that forbids DTDs and entities
    _safe_parser = etree.XMLParser(resolve_entities=False, dtd_validation=False, load_dtd=False, no_network=True)
    # Note: python-pptx/docx don't always use the default parser, but this helps catch some leaks
    etree.set_default_parser(_safe_parser)
except (ImportError, AttributeError):
    pass
