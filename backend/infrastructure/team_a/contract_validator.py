from numbers import Number

from infrastructure.team_a.exceptions import TeamAContractError


class TeamAContractValidator:

    RECOMMENDATIONS = {
        "APPROVE_RECOMMENDED",
        "REVIEW_REQUIRED",
    }

    EXCEPTION_CODES = {
        "NO_MATCH",
        "MULTIPLE_MATCHES",
        "DUPLICATE_RECORD",
        "VOLUME_MISMATCH",
        "PRODUCT_MISMATCH",
        "REFERENCE_UNAVAILABLE",
        "MISSING_FIELD",
    }

    SEVERITIES = {
        "INFO",
        "WARNING",
        "HIGH",
    }

    def validate_evaluate_request(self, payload: dict):
        if not isinstance(payload, dict):
            raise TeamAContractError("Payload must be an object.")

        record_id = payload.get("recordId")

        if not isinstance(record_id, str) or not record_id.strip():
            raise TeamAContractError(
                "recordId must be a non-empty string."
            )

        line_items = payload.get("lineItems", [])

        if line_items is None:
            raise TeamAContractError(
                "lineItems must be an array, not null."
            )

        if not isinstance(line_items, list):
            raise TeamAContractError(
                "lineItems must be an array."
            )

        seen_ids = set()

        for index, item in enumerate(line_items):
            if not isinstance(item, dict):
                raise TeamAContractError(
                    f"lineItems[{index}] must be an object."
                )

            line_item_id = item.get("lineItemId")

            if not isinstance(line_item_id, str):
                raise TeamAContractError(
                    f"lineItems[{index}].lineItemId "
                    "must be a string."
                )

            if not line_item_id.strip():
                raise TeamAContractError(
                    f"lineItems[{index}].lineItemId "
                    "must not be empty."
                )

            if line_item_id in seen_ids:
                raise TeamAContractError(
                    f"Duplicate lineItemId: {line_item_id}"
                )

            seen_ids.add(line_item_id)

        return payload

    def validate_evaluate_response(
        self,
        response: dict,
        *,
        request_payload: dict,
    ):
        if not isinstance(response, dict):
            raise TeamAContractError(
                "Team A response must be an object."
            )

        required_fields = (
            "recordId",
            "recommendation",
            "confidence",
            "modelVersion",
            "matchedTerminalLogId",
            "rationale",
            "mappedEntities",
            "exceptionIndicators",
        )

        self._require_fields(
            response,
            required_fields,
            "response",
        )

        if response["recordId"] != request_payload["recordId"]:
            raise TeamAContractError(
                "Response recordId must exactly echo request recordId."
            )

        if response["recommendation"] not in self.RECOMMENDATIONS:
            raise TeamAContractError(
                "Unsupported recommendation value."
            )

        confidence = response["confidence"]

        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, Number)
            or not 0 <= confidence <= 1
        ):
            raise TeamAContractError(
                "confidence must be between 0 and 1."
            )

        if not isinstance(response["modelVersion"], str):
            raise TeamAContractError(
                "modelVersion must be a string."
            )

        matched_terminal_log_id = response["matchedTerminalLogId"]

        if (
            matched_terminal_log_id is not None
            and not isinstance(matched_terminal_log_id, str)
        ):
            raise TeamAContractError(
                "matchedTerminalLogId must be a string or null."
            )

        if not isinstance(response["rationale"], str):
            raise TeamAContractError(
                "rationale must be a string."
            )

        mapped_entities = response["mappedEntities"]

        if not isinstance(mapped_entities, dict):
            raise TeamAContractError(
                "mappedEntities must be an object."
            )

        self._require_fields(
            mapped_entities,
            ("carrierCode", "lineItems"),
            "mappedEntities",
        )

        carrier_code = mapped_entities["carrierCode"]

        if (
            carrier_code is not None
            and not isinstance(carrier_code, str)
        ):
            raise TeamAContractError(
                "mappedEntities.carrierCode "
                "must be a string or null."
            )

        mapped_line_items = mapped_entities["lineItems"]

        if not isinstance(mapped_line_items, list):
            raise TeamAContractError(
                "mappedEntities.lineItems must be an array."
            )

        request_line_items = request_payload.get("lineItems", [])

        if len(mapped_line_items) != len(request_line_items):
            raise TeamAContractError(
                "mappedEntities.lineItems must contain "
                "one entry per request line item."
            )

        for index, mapped_item in enumerate(mapped_line_items):
            if not isinstance(mapped_item, dict):
                raise TeamAContractError(
                    f"mappedEntities.lineItems[{index}] "
                    "must be an object."
                )

            self._require_fields(
                mapped_item,
                ("lineItemId", "e3StockId", "standardName"),
                f"mappedEntities.lineItems[{index}]",
            )

            expected_id = request_line_items[index]["lineItemId"]

            if mapped_item["lineItemId"] != expected_id:
                raise TeamAContractError(
                    f"mappedEntities.lineItems[{index}].lineItemId "
                    "must exactly echo the request lineItemId."
                )

            for field_name in ("e3StockId", "standardName"):
                value = mapped_item[field_name]

                if (
                    value is not None
                    and not isinstance(value, str)
                ):
                    raise TeamAContractError(
                        f"mappedEntities.lineItems[{index}]."
                        f"{field_name} must be a string or null."
                    )

        exception_indicators = response["exceptionIndicators"]

        if not isinstance(exception_indicators, list):
            raise TeamAContractError(
                "exceptionIndicators must be an array."
            )

        for index, indicator in enumerate(exception_indicators):
            if not isinstance(indicator, dict):
                raise TeamAContractError(
                    f"exceptionIndicators[{index}] "
                    "must be an object."
                )

            self._require_fields(
                indicator,
                ("code", "severity", "message"),
                f"exceptionIndicators[{index}]",
            )

            if indicator["code"] not in self.EXCEPTION_CODES:
                raise TeamAContractError(
                    f"Unsupported exception code: "
                    f"{indicator['code']}"
                )

            if indicator["severity"] not in self.SEVERITIES:
                raise TeamAContractError(
                    f"Unsupported exception severity: "
                    f"{indicator['severity']}"
                )

            if not isinstance(indicator["message"], str):
                raise TeamAContractError(
                    f"exceptionIndicators[{index}].message "
                    "must be a string."
                )

            for optional_field in ("field", "lineItemId"):
                if optional_field in indicator:
                    value = indicator[optional_field]

                    if (
                        value is not None
                        and not isinstance(value, str)
                    ):
                        raise TeamAContractError(
                            f"exceptionIndicators[{index}]."
                            f"{optional_field} "
                            "must be a string or null."
                        )

        return response

    @staticmethod
    def _require_fields(obj, required_fields, path):
        missing = [
            field
            for field in required_fields
            if field not in obj
        ]

        if missing:
            raise TeamAContractError(
                f"{path} missing required fields: "
                + ", ".join(missing)
            )
