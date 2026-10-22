from unittest import TestCase

from core.exceptions.integration_exception import IntegrationException
from infrastructure.team_a.team_a_client import TeamAClient


VALID_RESPONSE = {
    "recordId": "rec_001",
    "recommendation": "APPROVE_RECOMMENDED",
    "confidence": 0.94,
    "modelVersion": "rules-v0.1",
    "matchedTerminalLogId": "TERM-001",
    "rationale": "Matched.",
    "mappedEntities": {},
    "exceptionIndicators": [],
}


class SequenceTransport:

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def __call__(
        self,
        *,
        url,
        payload,
        headers,
        timeout,
    ):
        outcome = self.outcomes[self.calls]
        self.calls += 1

        if isinstance(outcome, Exception):
            raise outcome

        return outcome


class TeamAClientTests(TestCase):

    def make_client(self, transport):
        self.sleeps = []

        return TeamAClient(
            base_url="https://team-a.test",
            api_key="test-key",
            transport=transport,
            sleep_fn=self.sleeps.append,
        )

    def test_success_does_not_retry(self):
        transport = SequenceTransport(
            [(200, VALID_RESPONSE)]
        )

        client = self.make_client(transport)

        result = client.evaluate(
            {"recordId": "rec_001"}
        )

        self.assertEqual(
            result["recordId"],
            "rec_001",
        )

        self.assertEqual(
            transport.calls,
            1,
        )

        self.assertEqual(
            self.sleeps,
            [],
        )

    def test_400_is_not_retried(self):
        transport = SequenceTransport(
            [
                (
                    400,
                    {
                        "code": "MALFORMED_REQUEST",
                        "message": "Bad request.",
                        "details": {},
                    },
                )
            ]
        )

        client = self.make_client(transport)

        with self.assertRaises(
            IntegrationException
        ) as context:
            client.evaluate(
                {"recordId": "rec_001"}
            )

        self.assertEqual(
            context.exception.status_code,
            400,
        )

        self.assertFalse(
            context.exception.retryable
        )

        self.assertEqual(
            transport.calls,
            1,
        )

    def test_401_is_not_retried(self):
        transport = SequenceTransport(
            [
                (
                    401,
                    {
                        "code": "UNAUTHORIZED",
                        "message": "Invalid API key.",
                        "details": {},
                    },
                )
            ]
        )

        client = self.make_client(transport)

        with self.assertRaises(
            IntegrationException
        ) as context:
            client.evaluate(
                {"recordId": "rec_001"}
            )

        self.assertEqual(
            context.exception.status_code,
            401,
        )

        self.assertEqual(
            transport.calls,
            1,
        )

    def test_422_is_not_retried(self):
        transport = SequenceTransport(
            [
                (
                    422,
                    {
                        "code": "INVALID_CHANGE_REQUEST",
                        "message": "Invalid change.",
                        "details": [],
                    },
                )
            ]
        )

        client = self.make_client(transport)

        with self.assertRaises(
            IntegrationException
        ) as context:
            client.evaluate(
                {"recordId": "rec_001"}
            )

        self.assertEqual(
            context.exception.status_code,
            422,
        )

        self.assertEqual(
            transport.calls,
            1,
        )

    def test_503_retries_then_succeeds(self):
        transport = SequenceTransport(
            [
                (
                    503,
                    {
                        "code": "SERVICE_UNAVAILABLE",
                        "message": "Try later.",
                        "details": {},
                    },
                ),
                (200, VALID_RESPONSE),
            ]
        )

        client = self.make_client(transport)

        result = client.evaluate(
            {"recordId": "rec_001"}
        )

        self.assertEqual(
            result["recordId"],
            "rec_001",
        )

        self.assertEqual(
            transport.calls,
            2,
        )

        self.assertEqual(
            self.sleeps,
            [2],
        )

    def test_timeout_retries_three_times(self):
        transport = SequenceTransport(
            [
                TimeoutError("timeout"),
                TimeoutError("timeout"),
                TimeoutError("timeout"),
                TimeoutError("timeout"),
            ]
        )

        client = self.make_client(transport)

        with self.assertRaises(
            IntegrationException
        ) as context:
            client.evaluate(
                {"recordId": "rec_001"}
            )

        self.assertEqual(
            context.exception.code,
            "TEAM_A_TIMEOUT",
        )

        self.assertTrue(
            context.exception.retryable
        )

        self.assertEqual(
            transport.calls,
            4,
        )

        self.assertEqual(
            self.sleeps,
            [2, 4, 8],
        )

    def test_503_exhaustion_is_retryable(self):
        error_response = (
            503,
            {
                "code": "SERVICE_UNAVAILABLE",
                "message": "Team A unavailable.",
                "details": {},
            },
        )

        transport = SequenceTransport(
            [
                error_response,
                error_response,
                error_response,
                error_response,
            ]
        )

        client = self.make_client(transport)

        with self.assertRaises(
            IntegrationException
        ) as context:
            client.evaluate(
                {"recordId": "rec_001"}
            )

        self.assertEqual(
            context.exception.code,
            "SERVICE_UNAVAILABLE",
        )

        self.assertTrue(
            context.exception.retryable
        )

        self.assertEqual(
            self.sleeps,
            [2, 4, 8],
        )

    def test_invalid_success_json_is_rejected(self):
        transport = SequenceTransport(
            [
                (
                    200,
                    "this is not JSON",
                )
            ]
        )

        client = self.make_client(transport)

        with self.assertRaises(
            IntegrationException
        ) as context:
            client.evaluate(
                {"recordId": "rec_001"}
            )

        self.assertEqual(
            context.exception.code,
            "TEAM_A_INVALID_RESPONSE",
        )
