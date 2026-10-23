from infrastructure.team_a.exceptions import TeamAContractError


class TeamAContractValidator:

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
