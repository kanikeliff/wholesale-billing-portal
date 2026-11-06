"""Build the immutable feedback snapshot while the billing record is locked."""
import json
from django.core.serializers.json import DjangoJSONEncoder


def build_feedback_payload(record, recommendation, decision, resulting_status):
    corrections = []
    for event in record.audit_events.filter(event_type="FIELD_CORRECTION").order_by("created_at", "pk"):
        item = {"field": event.field_name, "oldValue": event.old_value, "newValue": event.new_value}
        if event.line_item_id:
            item["lineItemId"] = str(event.line_item_id)
        corrections.append(item)
    payload = {
        "recordId": str(record.pk), "finalDecision": decision,
        "finalStatus": resulting_status, "correctedFields": corrections,
    }
    if recommendation:
        payload.update({
            "recommendation": recommendation.recommendation,
            "modelVersion": recommendation.model_version,
            "matchedTerminalLogId": recommendation.matched_terminal_log_id,
        })
    # Persist exactly the JSON values that the HTTP client will send, including
    # decimal/date values retained by older correction audit entries.
    return json.loads(json.dumps(payload, cls=DjangoJSONEncoder))
