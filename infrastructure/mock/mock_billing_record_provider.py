class MockBillingRecordProvider:

    def get_by_id(self, record_id):
        if record_id != "rec_001":
            return None

        return {
            "recordId": "rec_001",
            "status": "RECOMMENDATION_READY",

            "document": {
                "id": "doc_001",
                "fileName": "sample-bol.pdf",
                "fileUrl": "/media/sample-bol.pdf"
            },

            "fields": {
                "bolNumber": {
                    "rawValue": "BOL-45821",
                    "normalizedValue": "BOL-45821",
                    "confidence": 0.98,
                    "quality": "OK"
                },

                "contractLifting": {
                    "rawValue": "12345",
                    "normalizedValue": "12345",
                    "confidence": 0.95,
                    "quality": "OK"
                },

                "origin": {
                    "rawValue": "Albany Terminal",
                    "normalizedValue": "Albany Terminal",
                    "confidence": 0.97,
                    "quality": "OK"
                },

                "supplier": {
                    "rawValue": "Sunoco",
                    "normalizedValue": "Sunoco",
                    "confidence": 0.99,
                    "quality": "OK"
                },

                "carrier": {
                    "rawValue": "ABC Transport",
                    "normalizedValue": "ABC Transport",
                    "confidence": 0.68,
                    "quality": "LOW_CONFIDENCE"
                },

                "transactionDate": {
                    "rawValue": "09/29/2026",
                    "normalizedValue": "2026-09-29",
                    "confidence": 0.96,
                    "quality": "OK"
                },

                "destination": {
                    "rawValue": "Binghamton",
                    "normalizedValue": "Binghamton",
                    "confidence": 0.93,
                    "quality": "OK"
                }
            },

            "lineItems": [
                {
                    "lineItemId": 1,

                    "product": {
                        "rawValue": "RUL 87 ETH",
                        "normalizedValue": "RUL 87 ETH",
                        "confidence": 0.91,
                        "quality": "OK"
                    },

                    "grossGallons": {
                        "rawValue": "8550",
                        "normalizedValue": 8550.0,
                        "confidence": 0.94,
                        "quality": "OK"
                    },

                    "netGallons": {
                        "rawValue": "8500",
                        "normalizedValue": 8500.0,
                        "confidence": 0.95,
                        "quality": "OK"
                    },

                    "e3StockId": {
                        "rawValue": None,
                        "normalizedValue": None,
                        "confidence": None,
                        "quality": "MISSING"
                    }
                }
            ],

            "recommendation": {
                "recommendation": "REVIEW_REQUIRED",
                "confidence": 0.68,
                "rationale": "Gross gallons require manual review.",
                "matchedTerminalLogId": "TERM-TRX-884102",

                "mappedEntities": {
                    "carrierCode": "CR-ABC-01",

                    "lineItems": [
                        {
                            "lineItemId": 1,
                            "e3StockId": "UX",
                            "standardName": "87 Unleaded Regular"
                        }
                    ]
                },

                "exceptionIndicators": [
                    {
                        "code": "VOLUME_MISMATCH",
                        "severity": "WARNING",
                        "message": "Gross gallon difference exceeds tolerance.",
                        "field": "grossGallons",
                        "lineItemId": 1
                    }
                ]
            }
        }
