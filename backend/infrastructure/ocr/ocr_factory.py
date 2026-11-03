from .runtime_configuration import get_ocr_provider


def build_ocr_extractor():
    """Sample mode needs neither the live package nor model credentials."""
    provider = get_ocr_provider()
    if provider == "sample":
        from .sample_package_ocr_client import SamplePackageOCRClient
        return SamplePackageOCRClient().submit_document
    if provider == "live":
        from .live_ocr_client import LiveOCRClient
        return LiveOCRClient().submit_document
    raise ValueError("OCR_PROVIDER must be sample or live.")
