from unittest.mock import Mock

import requests
from django.test import SimpleTestCase

from infrastructure.team_a.client import TeamAClient
from infrastructure.team_a.exceptions import (
    TeamAIntegrationError,
    TeamAUnavailableError,
)


class TeamAClientTests(SimpleTestCase):

    def setUp(self):
        self.session = Mock()
        self.sleeper = Mock()

        self.client = TeamAClient(
            base_url="https://team-a.test",
            api_key="secret-key",
            timeout=10,
            session=self.session,
            sleeper=self.sleeper,
        )

        self.payload = {
            "recordId": "record-001",
            "lineItems": [
                {
                    "lineItemId":
                        "c7db5061-e167-4140-90ec-7fb48dd412ae"
                }
            ],
        }

    def response(self, status_code, body):
        response = Mock()
        response.status_code = status_code
        response.json.return_value = body
        return response

    def test_sends_api_key_and_timeout(self):
        self.session.post.return_value = self.response(
            200,
            {
                "recordId": "record-001",
                "recommendation": "APPROVE_RECOMMENDED",
            },
        )

        self.client.evaluate(self.payload)

        _, kwargs = self.session.post.call_args

        self.assertEqual(
            kwargs["headers"]["X-API-Key"],
            "secret-key",
        )
        self.assertEqual(
            kwargs["timeout"],
            10,
        )

    def test_400_is_not_retried(self):
        self.session.post.return_value = self.response(
            400,
            {
                "code": "INVALID_REQUEST",
                "message": "Bad request",
            },
        )

        with self.assertRaises(TeamAIntegrationError):
            self.client.evaluate(self.payload)

        self.assertEqual(
            self.session.post.call_count,
            1,
        )

    def test_503_is_retried(self):
        self.session.post.side_effect = [
            self.response(503, {}),
            self.response(200, {
                "recordId": "record-001",
                "recommendation": "APPROVE_RECOMMENDED",
            }),
        ]

        result = self.client.evaluate(self.payload)

        self.assertEqual(
            result["recommendation"],
            "APPROVE_RECOMMENDED",
        )

        self.assertEqual(
            self.session.post.call_count,
            2,
        )

        self.sleeper.assert_called_once_with(2)

    def test_timeout_is_retried(self):
        self.session.post.side_effect = [
            requests.Timeout(),
            self.response(
                200,
                {
                    "recordId": "record-001",
                    "recommendation":
                        "APPROVE_RECOMMENDED",
                },
            ),
        ]

        result = self.client.evaluate(self.payload)

        self.assertEqual(
            result["recordId"],
            "record-001",
        )

        self.sleeper.assert_called_once_with(2)

    def test_retry_exhaustion_raises_unavailable(self):
        self.session.post.return_value = self.response(
            503,
            {},
        )

        with self.assertRaises(
            TeamAUnavailableError
        ):
            self.client.evaluate(self.payload)

        self.assertEqual(
            self.session.post.call_count,
            4,
        )

        self.assertEqual(
            [call.args[0] for call in self.sleeper.call_args_list],
            [2, 4, 8],
        )
