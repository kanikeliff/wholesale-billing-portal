from datetime import datetime
from decimal import Decimal, InvalidOperation


class BolLabAdapter:
    """
    Converts OCR bol-lab-v1 output into Team B canonical format.
    """

    def adapt(self, extraction: dict) -> dict:
        if not isinstance(extraction, dict):
            raise ValueError("OCR extraction must be an object.")

        products = extraction.get("products") or []

        if not isinstance(products, list):
            raise ValueError("OCR products must be an array.")

        return {
            "fields": {
                "bolNumber": self._field(
                    extraction.get("bol_number")
                ),
                "contractLifting": self._field(
                    extraction.get("contract_number")
                ),
                "origin": self._field(
                    extraction.get("origin")
                ),
                "supplier": self._field(
                    extraction.get("supplier")
                ),
                "carrier": self._field(
                    extraction.get("carrier")
                ),
                "transactionDate": self._field(
                    extraction.get("transaction_date"),
                    normalizer=self._normalize_date,
                ),
                "destination": self._field(
                    extraction.get("destination")
                ),
            },
            "lineItems": [
                self._line_item(product, index)
                for index, product in enumerate(
                    products,
                    start=1,
                )
            ],
        }

    def _line_item(self, product, line_number):
        if not isinstance(product, dict):
            raise ValueError(
                "Each OCR product must be an object."
            )

        return {
            "lineNumber": line_number,
            "product": self._field(
                product.get("product")
            ),
            "netGallons": self._field(
                product.get("net_gallons"),
                normalizer=self._normalize_number,
            ),
            "grossGallons": self._field(
                product.get("gross_gallons"),
                normalizer=self._normalize_number,
            ),
            "e3StockId": self._field(
                product.get("e3_stock_id")
            ),
            "ocrEvidence": {
                "productCode": self._clean_string(
                    product.get("product_code")
                )
            },
        }

    def _field(self, raw_value, normalizer=None):
        cleaned = self._clean_value(raw_value)

        if cleaned is None:
            return {
                "rawValue": raw_value,
                "normalizedValue": None,
                "confidence": None,
                "unresolved": True,
            }

        normalized = (
            normalizer(cleaned)
            if normalizer
            else cleaned
        )

        return {
            "rawValue": raw_value,
            "normalizedValue": normalized,
            "confidence": None,
            "unresolved": normalized is None,
        }

    @staticmethod
    def _clean_value(value):
        if value is None:
            return None

        if isinstance(value, str):
            value = value.strip()

            if not value:
                return None

        return value

    def _clean_string(self, value):
        value = self._clean_value(value)

        if value is None:
            return None

        return str(value)

    @staticmethod
    def _normalize_number(value):
        try:
            number = Decimal(
                str(value)
                .replace(",", "")
                .strip()
            )
        except (InvalidOperation, ValueError, TypeError):
            return None

        return float(number)

    @staticmethod
    def _normalize_date(value):
        if not isinstance(value, str):
            return None

        value = value.strip()

        formats = (
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%m/%d/%y",
            "%b %d, %Y",
            "%B %d, %Y",
        )

        for date_format in formats:
            try:
                parsed = datetime.strptime(
                    value,
                    date_format,
                )
                return parsed.date().isoformat()
            except ValueError:
                continue

        return None
