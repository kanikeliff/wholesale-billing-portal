from numbers import Number

from core.exceptions.integration_exception import IntegrationException


class TeamAMapper:

    TOP_LEVEL_FIELDS = (
        "bolNumber",
        "contractLifting",
        "origin",
        "supplier",
        "carrier",
        "transactionDate",
        "destination",
    )

    LINE_ITEM_FIELDS = (
        "product",
        "e3StockId",
        "grossGallons",
        "netGallons",
    )

    RECOMMENDATIONS = {
        "APPROVE_RECOMMENDED",
        "REVIEW_REQUIRED",
    }

    FIELD_QUALITIES = {
        "OK",
        "LOW_CONFIDENCE",
        "MISSING",
        "UNREADABLE",
        "INVALID",
    }

    def to_evaluation_request(self, record):
        record_id = record.get("recordId") or record.get("record_id")

        if not record_id:
            raise IntegrationException(
                "TEAM_A_INVALID_REQUEST",
                "recordId is required before calling Team A.",
                details={"field": "recordId"},
                status_code=400,
                retryable=False,
            )

        fields = record.get("fields") or {}

        payload = {
            "recordId": str(record_id),
            "lineItems": [],
        }

        ocr_confidence = {}
        field_quality = {}

        for field_name in self.TOP_LEVEL_FIELDS:
            field_data = fields.get(field_name)

            payload[field_name] = self._value(field_data)

            confidence = self._confidence(field_data)
            quality = self._quality(field_data)

            if confidence is not None:
                ocr_confidence[field_name] = confidence

            if quality is not None:
                field_quality[field_name] = quality

        if ocr_confidence:
            payload["ocrConfidence"] = ocr_confidence

        if field_quality:
            payload["fieldQuality"] = field_quality

        line_items = record.get("lineItems")

        if not isinstance(line_items, list):
            line_items = []

        for line_item in line_items:
            payload["lineItems"].append(
                self._map_line_item(line_item)
            )

        return payload

    def from_evaluation_response(
        self,
        response,
        *,
        expected_record_id=None,
    ):
        if not isinstance(response, dict):
            self._invalid_response(
                "Team A response must be a JSON object."
            )

        required_fields = (
            "recordId",
            "recommendation",
            "confidence",
            "modelVersion",
            "rationale",
            "mappedEntities",
            "exceptionIndicators",
        )

        missing = [
            field
            for field in required_fields
            if field not in response
        ]

        if missing:
            self._invalid_response(
                "Team A response is missing required fields.",
                {"missingFields": missing},
            )

        record_id = response.get("recordId")

        if expected_record_id is not None:
            if str(record_id) != str(expected_record_id):
                self._invalid_response(
                    "Team A response recordId does not match the request.",
                    {
                        "expectedRecordId": str(expected_record_id),
                        "actualRecordId": record_id,
                    },
                )

        recommendation = response.get("recommendation")

        if recommendation not in self.RECOMMENDATIONS:
            self._invalid_response(
                "Team A returned an unsupported recommendation value.",
                {"recommendation": recommendation},
            )

        confidence = response.get("confidence")

        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, Number)
            or not 0 <= confidence <= 1
        ):
            self._invalid_response(
                "Team A confidence must be between 0 and 1.",
                {"confidence": confidence},
            )

        if not isinstance(response.get("modelVersion"), str):
            self._invalid_response(
                "Team A modelVersion must be a string."
            )

        if not isinstance(response.get("rationale"), str):
            self._invalid_response(
                "Team A rationale must be a string."
            )

        if not isinstance(response.get("mappedEntities"), dict):
            self._invalid_response(
                "Team A mappedEntities must be an object."
            )

        exceptions = response.get("exceptionIndicators")

        if not isinstance(exceptions, list):
            self._invalid_response(
                "Team A exceptionIndicators must be an array."
            )

        for exception in exceptions:
            if not isinstance(exception, dict):
                self._invalid_response(
                    "Each Team A exception indicator must be an object."
                )

            for required in ("code", "severity", "message"):
                if required not in exception:
                    self._invalid_response(
                        "Team A exception indicator is malformed.",
                        {
                            "missingField": required,
                            "exception": exception,
                        },
                    )

        return response

    def _map_line_item(self, line_item):
        if not isinstance(line_item, dict):
            return {}

        result = {
            "lineItemId": line_item.get("lineItemId"),
        }

        ocr_confidence = {}
        field_quality = {}

        for field_name in self.LINE_ITEM_FIELDS:
            field_data = line_item.get(field_name)

            result[field_name] = self._value(field_data)

            confidence = self._confidence(field_data)
            quality = self._quality(field_data)

            if confidence is not None:
                ocr_confidence[field_name] = confidence

            if quality is not None:
                field_quality[field_name] = quality

        if ocr_confidence:
            result["ocrConfidence"] = ocr_confidence

        if field_quality:
            result["fieldQuality"] = field_quality

        return result

    def _value(self, field_data):
        if isinstance(field_data, dict):
            return field_data.get("normalizedValue")

        return field_data

    def _confidence(self, field_data):
        if not isinstance(field_data, dict):
            return None

        confidence = field_data.get("confidence")

        if isinstance(confidence, bool):
            return None

        if isinstance(confidence, Number):
            return confidence

        return None

    def _quality(self, field_data):
        if not isinstance(field_data, dict):
            return None

        quality = field_data.get("quality")

        if quality in self.FIELD_QUALITIES:
            return quality

        return None

    def _invalid_response(self, message, details=None):
        raise IntegrationException(
            "TEAM_A_INVALID_RESPONSE",
            message,
            details=details,
            status_code=502,
            retryable=False,
        )
