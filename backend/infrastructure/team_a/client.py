import time

import requests

from infrastructure.team_a.contract_validator import (
    TeamAContractValidator,
)
from infrastructure.team_a.exceptions import (
    TeamAIntegrationError,
    TeamAUnavailableError,
)


class TeamAClient:

    def __init__(
        self,
        *,
        base_url,
        api_key,
        timeout=10,
        session=None,
        sleeper=None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.session = session or requests.Session()
        self.sleeper = sleeper or time.sleep
        self.validator = TeamAContractValidator()

    def evaluate(self, payload: dict) -> dict:
        self.validator.validate_evaluate_request(payload)

        url = (
            f"{self.base_url}"
            "/api/v1/recommendations/evaluate"
        )

        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

        backoff = (0, 2, 4, 8)

        last_error = None

        for attempt, delay in enumerate(backoff):
            if delay:
                self.sleeper(delay)

            try:
                response = self.session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
            except requests.Timeout as exc:
                last_error = exc

                if attempt == len(backoff) - 1:
                    break

                continue

            except requests.RequestException as exc:
                raise TeamAIntegrationError(
                    f"Team A request failed: {exc}"
                ) from exc

            if 200 <= response.status_code < 300:
                return response.json()

            if 400 <= response.status_code < 500:
                self._raise_non_retryable(response)

            if response.status_code >= 500:
                last_error = TeamAUnavailableError(
                    f"Team A returned HTTP "
                    f"{response.status_code}"
                )

                if attempt == len(backoff) - 1:
                    break

                continue

            raise TeamAIntegrationError(
                f"Unexpected Team A HTTP status: "
                f"{response.status_code}"
            )

        raise TeamAUnavailableError(
            "Team A unavailable after retry exhaustion."
        ) from last_error

    def _raise_non_retryable(self, response):
        try:
            body = response.json()
        except ValueError:
            body = {}

        code = body.get("code", "TEAM_A_ERROR")
        message = body.get(
            "message",
            f"Team A returned HTTP {response.status_code}",
        )

        raise TeamAIntegrationError(
            f"{code}: {message}"
        )
