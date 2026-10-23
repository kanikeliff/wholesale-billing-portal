from django.test import SimpleTestCase

from infrastructure.team_a.contract_validator import (
    TeamAContractValidator,
)
from infrastructure.team_a.exceptions import TeamAContractError


class TeamAContractValidatorTests(SimpleTestCase):

    def setUp(self):
        self.validator = TeamAContractValidator()

    def valid_payload(self):
        return {
            "recordId": "record-001",
            "lineItems": [
                {
                    "lineItemId":
                        "c7db5061-e167-4140-90ec-7fb48dd412ae",
                    "product": "ULSD",
                }
            ],
        }

    def test_uuid_string_line_item_id_is_valid(self):
        self.validator.validate_evaluate_request(
            self.valid_payload()
        )

    def test_numeric_line_item_id_is_rejected(self):
        payload = self.valid_payload()
        payload["lineItems"][0]["lineItemId"] = 1

        with self.assertRaises(TeamAContractError):
            self.validator.validate_evaluate_request(
                payload
            )

    def test_empty_line_item_id_is_rejected(self):
        payload = self.valid_payload()
        payload["lineItems"][0]["lineItemId"] = ""

        with self.assertRaises(TeamAContractError):
            self.validator.validate_evaluate_request(
                payload
            )

    def test_duplicate_line_item_id_is_rejected(self):
        payload = self.valid_payload()

        payload["lineItems"].append(
            {
                "lineItemId":
                    "c7db5061-e167-4140-90ec-7fb48dd412ae",
                "product": "Gasoline",
            }
        )

        with self.assertRaises(TeamAContractError):
            self.validator.validate_evaluate_request(
                payload
            )
