from infrastructure.team_a.recommendation_provider import  (RecommendationProvider)

class MockTeamAdapter(RecommendationProvider):
    def evaluate(self, record):
        record_id = str (
            record.get("recordId")
            or record.get("record_id")
            or "mock-record"

        )
        return {
            "recordId": record_id,
            "recommendation": "APPROVE_RECOMMENDED",
            "confidence": 0.94,
            "modelVersion": "mock-v1",
            "matchedTerminalLogId": "TERM-001",
            "rationale": (
                "Carrier and product values matched "
                "the available reference data."
            ),

            "mappedEntities": {
                "carrierCode": "MUN",

                "lineItems": [
                    {
                        "lineItemId": 1,
                        "e3StockId": "UX",
                        "standardName": "87 Gas"
                    }
                ]
            },

            "exceptionIndicators": []
        }