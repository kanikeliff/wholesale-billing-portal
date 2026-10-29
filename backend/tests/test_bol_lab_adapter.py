from django.test import SimpleTestCase

from infrastructure.ocr.bol_lab_adapter import (
    BolLabAdapter,
)


class BolLabAdapterTests(SimpleTestCase):

    def setUp(self):
        self.adapter = BolLabAdapter()

    def test_maps_bol_lab_output(self):
        extraction = {
            "bol_number": "00000831062",
            "contract_number": None,
            "origin": "ETP SYRACUSE - 34015",
            "supplier": "MONROE ENERGY LLC",
            "carrier": "MIRABITO ENERGY PRODUCTS",
            "transaction_date": "2026-09-17",
            "destination": "CONTRACT VARIOUS NY",
            "products": [
                {
                    "product": "Gasoline",
                    "product_code": "403100",
                    "net_gallons": "7473",
                    "gross_gallons": "7500",
                    "e3_stock_id": None,
                },
                {
                    "product": "Gasoline",
                    "product_code": "403400",
                    "net_gallons": "990",
                    "gross_gallons": "1000",
                    "e3_stock_id": None,
                },
            ],
        }

        result = self.adapter.adapt(extraction)

        self.assertEqual(
            result["fields"]["bolNumber"][
                "normalizedValue"
            ],
            "00000831062",
        )

        self.assertEqual(
            result["fields"]["transactionDate"][
                "normalizedValue"
            ],
            "2026-09-17",
        )

        self.assertEqual(
            len(result["lineItems"]),
            2,
        )

        self.assertEqual(
            result["lineItems"][0]["lineNumber"],
            1,
        )

        self.assertEqual(
            result["lineItems"][1]["lineNumber"],
            2,
        )

        self.assertEqual(
            result["lineItems"][0]["netGallons"][
                "normalizedValue"
            ],
            7473.0,
        )

        self.assertEqual(
            result["lineItems"][0]["ocrEvidence"][
                "productCode"
            ],
            "403100",
        )

    def test_null_is_unresolved(self):
        result = self.adapter.adapt(
            {
                "contract_number": None,
                "products": [],
            }
        )

        field = result["fields"]["contractLifting"]

        self.assertIsNone(
            field["normalizedValue"]
        )
        self.assertIsNone(
            field["confidence"]
        )
        self.assertTrue(
            field["unresolved"]
        )

    def test_empty_string_is_unresolved(self):
        result = self.adapter.adapt(
            {
                "carrier": "   ",
                "products": [],
            }
        )

        self.assertTrue(
            result["fields"]["carrier"]["unresolved"]
        )

    def test_date_is_normalized(self):
        result = self.adapter.adapt(
            {
                "transaction_date": "09/17/2026",
                "products": [],
            }
        )

        self.assertEqual(
            result["fields"]["transactionDate"][
                "normalizedValue"
            ],
            "2026-09-17",
        )

    def test_product_code_is_not_e3(self):
        result = self.adapter.adapt(
            {
                "products": [
                    {
                        "product": "ULSD",
                        "product_code": "403100",
                        "e3_stock_id": None,
                    }
                ]
            }
        )

        line = result["lineItems"][0]

        self.assertIsNone(
            line["e3StockId"]["normalizedValue"]
        )

        self.assertEqual(
            line["ocrEvidence"]["productCode"],
            "403100",
        )
