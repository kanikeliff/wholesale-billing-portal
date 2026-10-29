from infrastructure.team_a.recommendation_provider import (
    RecommendationProvider,
)


class MockTeamAAdapter(RecommendationProvider):

    @staticmethod
    def _value(field):
        if isinstance(field, dict):
            return field.get("normalizedValue")
        return field

    def evaluate(self, record):
        record_id = str(
            record.get("recordId")
            or record.get("record_id")
            or "mock-record"
        )

        fields = record.get("fields") or {}
        line_items = record.get("lineItems") or []

        exceptions = []
        mapped_lines = []

        contract = self._value(
            fields.get("contractLifting")
        )

        if not contract:
            exceptions.append({
                "code": "MISSING_CONTRACT_LIFTING",
                "severity": "WARNING",
                "message": "Contract/Lifting is missing.",
                "field": "contractLifting",
            })

        for item in line_items:
            line_id = item.get("lineItemId")
            e3 = self._value(item.get("e3StockId"))

            mapped_lines.append({
                "lineItemId": line_id,
                "e3StockId": e3,
            })

            if not e3:
                exceptions.append({
                    "code": "MISSING_E3_STOCK_ID",
                    "severity": "WARNING",
                    "message": (
                        "E3 Stock ID is missing. "
                        "Entity resolution is required."
                    ),
                    "field": "e3StockId",
                    "lineItemId": line_id,
                })

        return {
            "recordId": record_id,
            "recommendation": "REVIEW_REQUIRED",
            "confidence": 0.0,
            "modelVersion": "mock-contract-v2",
            "matchedTerminalLogId": None,
            "rationale": (
                "Contract simulation only. "
                "No real terminal matching, entity resolution, "
                "or decision confidence was calculated. "
                "Human review is required."
            ),
            "mappedEntities": {
                "lineItems": mapped_lines,
            },
            "exceptionIndicators": exceptions,
        }


MockTeamAdapter = MockTeamAAdapter
