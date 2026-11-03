"""Offline HTTP doubles exercise the real Team B service, adapter and ORM."""
import json
from pathlib import Path
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from apps.billing.models import BillingRecord
from apps.persistence.models import Recommendation
from application.services.ocr_processing_service import OCRProcessingService
from infrastructure.database.django_billing_record_repository import DjangoBillingRecordRepository
from infrastructure.ocr.bol_lab_adapter import BolLabAdapter
from infrastructure.team_a.client import TeamAClient
from infrastructure.team_a.team_a_adapter import TeamAAdapter
from tests.test_team_a_adapter import successful_response


class TeamABackendIntegrationTests(APITestCase):
    def setUp(self):
        self.record = BillingRecord.objects.create(status="OCR_PROCESSING")
        extraction = json.loads((Path(__file__).parents[1] /
            "infrastructure/ocr/sample_package/extractions/Sample_BOL_3.json").read_text())
        OCRProcessingService(adapter=BolLabAdapter(),
            billing_record_repository=DjangoBillingRecordRepository()
        ).persist_extraction_for_record(str(self.record.record_id), extraction)
        self.lines = list(self.record.line_items.order_by("line_number"))
        self.session = Mock()
        provider = TeamAAdapter(TeamAClient(
            base_url="https://team-a.test", api_key="unit-test-placeholder",
            session=self.session, sleeper=lambda _: None,
        ))
        replacement = patch("presentation.api.billing_views.recommendation_service.recommendation_provider", provider)
        replacement.start()
        self.addCleanup(replacement.stop)
        self.client.force_authenticate(user=User(username="test-reviewer"))
        self.url = f"/api/v1/billing-records/{self.record.record_id}/evaluate/"

    def upstream_response(self, status, body):
        self.session.post.return_value = Mock(status_code=status)
        self.session.post.return_value.json.return_value = body

    def test_valid_response_persists_with_stable_line_ids(self):
        # Reuse existing synthetic unit response; no live credential/provider.
        body = successful_response()
        body["recordId"] = str(self.record.record_id)
        body["mappedEntities"]["lineItems"] = [
            {"lineItemId": str(line.line_item_id), "e3StockId": None, "standardName": None}
            for line in self.lines
        ]
        body["exceptionIndicators"] = []
        self.upstream_response(200, body)
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, "RECOMMENDATION_READY")
        stored = Recommendation.objects.get(billing_record=self.record)
        self.assertEqual(stored.raw_response, body)
        self.assertEqual(stored.revision, 1)
        self.assertTrue(stored.is_current)
        payload = self.session.post.call_args.kwargs["json"]
        self.assertEqual([line["lineItemId"] for line in payload["lineItems"]],
                         [str(line.line_item_id) for line in self.lines])

    def test_authentication_failure_is_controlled_and_not_persisted(self):
        self.upstream_response(401, {"code": "UNAUTHORIZED", "message": "Unauthorized"})
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["code"], "UNAUTHORIZED")
        self.assertEqual(response.data["details"]["upstreamStatus"], 401)
        self.assertEqual(self.session.post.call_count, 1)
        self.assertFalse(Recommendation.objects.filter(billing_record=self.record).exists())

    def test_contract_rejection_is_distinct_from_authentication_failure(self):
        self.upstream_response(422, {"code": "INVALID_REQUEST", "message": "Invalid request"})
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["code"], "INVALID_REQUEST")
        self.assertEqual(response.data["details"]["upstreamStatus"], 422)
        self.assertEqual(self.session.post.call_count, 1)
        self.assertFalse(Recommendation.objects.filter(billing_record=self.record).exists())

    def test_retry_exhaustion_remains_pending_without_a_recommendation(self):
        self.upstream_response(503, {})
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.data["pending"])
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, "RECOMMENDATION_PENDING")
        self.assertEqual(self.session.post.call_count, 4)
        self.assertFalse(Recommendation.objects.filter(billing_record=self.record).exists())

    def test_invalid_line_mapping_is_rejected_before_persistence(self):
        body = successful_response()
        body["recordId"] = str(self.record.record_id)
        self.upstream_response(200, body)
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["code"], "TEAM_A_INVALID_RESPONSE")
        self.assertFalse(Recommendation.objects.filter(billing_record=self.record).exists())
