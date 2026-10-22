from unittest import TestCase

from core.exceptions.integration_exception import IntegrationException
from infrastructure.team_a.team_a_adapter import TeamAAdapter
from infrastructure.team_a.team_a_mapper import TeamAMapper


class FakeTeamAClient:

    def __init__(self, response):
        self.response = response
        self.last_payload = None

    def evaluate(self, payload):
        self.last_payload = payload
        return self.response


def sample_record():
    return {
        "recordId": "rec_001",
        "fields": {
            "bolNumber": {
                "normalizedValue": "BOL-45821",
                "confidence": 0.98,
                "quality": "OK",
            },
            "contractLifting": {
                "normalizedValue": "12345",
                "confidence": 0.95,
                "quality": "OK",
            },
            "origin": {
                "normalizedValue": "Albany Terminal",
                "confidence": 0.97,
                "quality": "OK",
            },
            "supplier": {
                "normalizedValue": "Sunoco",
                "confidence": 0.99,
                "quality": "OK",
            },
            "carrier": {
                "normalizedValue": "ABC Transport",
                "confidence": 0.68,
                "quality": "LOW_CONFIDENCE",
            },
            "transactionDate": {
                "normalizedValue": "2026-09-29",
                "confidence": 0.96,
                "quality": "OK",
            },
            "destination": {
                "normalizedValue": "Binghamton",
                "confidence": 0.93,
                "quality": "OK",
            },
        },
        "lineItems": [
            {
                "lineItemId": 1,
                "product": {
                    "normalizedValue": "RUL 87 ETH",
                    "confidence": 0.91,
                    "quality": "OK",
                },
                "grossGallons": {
                    "normalizedValue": 8550.0,
                    "confidence": 0.94,
                    "quality": "OK",
                },
                "netGallons": {
                    "normalizedValue": 8500.0,
                    "confidence": 0.95,
                    "quality": "OK",
                },
                "e3StockId": {
                    "normalizedValue": None,
                    "confidence": None,
                    "quality": "MISSING",
                },
            }
        ],
    }


def successful_response():
    return {
        "recordId": "rec_001",
        "recommendation": "REVIEW_REQUIRED",
        "confidence": 0.68,
        "modelVersion": "rules-v0.1",
        "matchedTerminalLogId": "TERM-TRX-884102",
        "rationale": "Record requires review.",
        "mappedEntities": {
            "carrierCode": "CR-ABC-01",
            "lineItems": [],
        },
        "exceptionIndicators": [
            {
                "code": "VOLUME_MISMATCH",
                "severity": "WARNING",
                "message": "Gross gallon difference exceeds tolerance.",
                "field": "grossGallons",
                "lineItemId": 1,
            }
        ],
    }


class TeamAMapperTests(TestCase):

    def test_maps_record_to_team_a_contract(self):
        mapper = TeamAMapper()

        payload = mapper.to_evaluation_request(
            sample_record()
        )

        self.assertEqual(
            payload["recordId"],
            "rec_001",
        )

        self.assertEqual(
            payload["carrier"],
            "ABC Transport",
        )

        self.assertEqual(
            payload["fieldQuality"]["carrier"],
            "LOW_CONFIDENCE",
        )

        self.assertEqual(
            payload["lineItems"][0]["e3StockId"],
            None,
        )

        self.assertEqual(
            payload["lineItems"][0]["fieldQuality"]["e3StockId"],
            "MISSING",
        )

    def test_line_items_is_always_array(self):
        mapper = TeamAMapper()

        record = sample_record()
        record["lineItems"] = None

        payload = mapper.to_evaluation_request(record)

        self.assertEqual(
            payload["lineItems"],
            [],
        )


class TeamAAdapterTests(TestCase):

    def test_successful_response_is_returned(self):
        client = FakeTeamAClient(
            successful_response()
        )

        adapter = TeamAAdapter(client)

        result = adapter.evaluate(
            sample_record()
        )

        self.assertEqual(
            result["recommendation"],
            "REVIEW_REQUIRED",
        )

        self.assertEqual(
            client.last_payload["recordId"],
            "rec_001",
        )

    def test_mismatched_record_id_is_rejected(self):
        response = successful_response()
        response["recordId"] = "rec_other"

        adapter = TeamAAdapter(
            FakeTeamAClient(response)
        )

        with self.assertRaises(
            IntegrationException
        ) as context:
            adapter.evaluate(sample_record())

        self.assertEqual(
            context.exception.code,
            "TEAM_A_INVALID_RESPONSE",
        )

    def test_missing_response_field_is_rejected(self):
        response = successful_response()
        del response["modelVersion"]

        adapter = TeamAAdapter(
            FakeTeamAClient(response)
        )

        with self.assertRaises(
            IntegrationException
        ) as context:
            adapter.evaluate(sample_record())

        self.assertEqual(
            context.exception.code,
            "TEAM_A_INVALID_RESPONSE",
        )
