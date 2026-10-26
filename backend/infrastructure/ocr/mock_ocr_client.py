from infrastructure.ocr.ocr_client import OCRClient


class MockOCRClient(OCRClient):
    """
    Development-only OCR provider.

    It accepts a real uploaded document but returns a fixed,
    realistic OCR extraction so the complete upload -> normalize
    -> PostgreSQL pipeline can be tested without the live OCR service.
    """

    def submit_document(
        self,
        *,
        document_id: str,
        file_bytes: bytes,
        filename: str,
    ) -> dict:
        return {
            "extraction": {
                "bol_number": f"MOCK-{document_id[:8]}",
                "contract_number": "LIFT-MOCK-001",
                "origin": "ETP Fullerton, PA terminal",
                "supplier": "Marathon",
                "carrier": "Penn Tank Lines",
                "transaction_date": "2026-09-17",
                "destination": "Pennsylvania",
                "products": [
                    {
                        "product": "B2 Diesel Clear",
                        "product_code": "BD2",
                        "e3_stock_id": "BD2",
                        "net_gallons": "7443",
                        "gross_gallons": "7500",
                    }
                ],
            }
        }

    def get_job(self, job_id: str) -> dict:
        raise NotImplementedError(
            "MockOCRClient returns synchronous OCR results."
        )
