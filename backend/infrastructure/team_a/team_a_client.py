import json
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.exceptions.integration_exception import IntegrationException


class TeamAClient:

    EVALUATE_PATH = "/api/v1/recommendations/evaluate"

    def __init__(
        self,
        base_url,
        api_key,
        *,
        timeout=10,
        retry_delays=(2, 4, 8),
        sleep_fn=time.sleep,
        transport=None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.retry_delays = tuple(retry_delays)
        self.sleep_fn = sleep_fn
        self.transport = transport or self._default_transport

    def evaluate(self, payload):
        url = f"{self.base_url}{self.EVALUATE_PATH}"

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-Key": self.api_key,
        }

        retry_index = 0

        while True:
            try:
                status_code, response_body = self.transport(
                    url=url,
                    payload=payload,
                    headers=headers,
                    timeout=self.timeout,
                )

            except (TimeoutError, socket.timeout, URLError) as error:
                if retry_index < len(self.retry_delays):
                    self.sleep_fn(
                        self.retry_delays[retry_index]
                    )
                    retry_index += 1
                    continue

                raise IntegrationException(
                    "TEAM_A_TIMEOUT",
                    "Team A did not respond before the retry limit was exhausted.",
                    details={"reason": str(error)},
                    status_code=503,
                    retryable=True,
                ) from error

            parsed_body = self._parse_body(
                response_body,
                status_code=status_code,
            )

            if 200 <= status_code < 300:
                if not isinstance(parsed_body, dict):
                    raise IntegrationException(
                        "TEAM_A_INVALID_RESPONSE",
                        "Team A returned a non-object JSON response.",
                        details=None,
                        status_code=502,
                        retryable=False,
                    )

                return parsed_body

            error = self._build_error(
                status_code,
                parsed_body,
            )

            if (
                status_code >= 500
                and retry_index < len(self.retry_delays)
            ):
                self.sleep_fn(
                    self.retry_delays[retry_index]
                )
                retry_index += 1
                continue

            raise error

    def _build_error(self, status_code, body):
        if isinstance(body, dict):
            code = body.get("code") or "TEAM_A_ERROR"
            message = (
                body.get("message")
                or "Team A request failed."
            )
            details = body.get("details")
        else:
            code = "TEAM_A_ERROR"
            message = "Team A request failed."
            details = {"response": body}

        return IntegrationException(
            code,
            message,
            details=details,
            status_code=status_code,
            retryable=status_code >= 500,
        )

    def _parse_body(self, body, *, status_code):
        if isinstance(body, dict):
            return body

        if body in (None, ""):
            return {}

        try:
            return json.loads(body)

        except (TypeError, json.JSONDecodeError) as error:
            if 200 <= status_code < 300:
                raise IntegrationException(
                    "TEAM_A_INVALID_RESPONSE",
                    "Team A returned invalid JSON.",
                    details={"response": str(body)},
                    status_code=502,
                    retryable=False,
                ) from error

            return {
                "code": "TEAM_A_ERROR",
                "message": "Team A returned an invalid error response.",
                "details": {
                    "response": str(body),
                },
            }

    def _default_transport(
        self,
        *,
        url,
        payload,
        headers,
        timeout,
    ):
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urlopen(
                request,
                timeout=timeout,
            ) as response:
                return (
                    response.status,
                    response.read().decode("utf-8"),
                )

        except HTTPError as error:
            return (
                error.code,
                error.read().decode("utf-8"),
            )
