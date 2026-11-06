"""Query-count and contract regressions for backend read/queue hot paths."""
from datetime import timedelta
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.billing.models import BillingRecord, LineItem
from apps.persistence.models import AuditEvent, Document, ExtractedField, HumanDecision, OCRJob
from application.services.feedback_delivery_service import FeedbackDeliveryService
from infrastructure.database.django_billing_record_repository import DjangoBillingRecordRepository


class BillingReadPerformanceTests(TestCase):
    def setUp(self):
        self.repository = DjangoBillingRecordRepository()

    def add_record(self, number):
        record = BillingRecord.objects.create(bol_number=f"QUERY-{number}", status="REJECTED")
        line = LineItem.objects.create(billing_record=record, line_number=1, product="ULSD", e3_stock_id="UD")
        document = Document.objects.create(billing_record=record, original_filename="sample.pdf")
        OCRJob.objects.create(document=document, status="FAILED", error_code="old", raw_result={"large": "x" * 10000})
        latest_job = OCRJob.objects.create(document=document, status="COMPLETED", raw_result={"large": "x" * 10000})
        ExtractedField.objects.create(billing_record=record, line_item=line, field_name="product",
                                      raw_value="DIESEL", quality="LOW_CONFIDENCE", confidence=Decimal("0.99"),
                                      metadata={"large": "x" * 10000})
        AuditEvent.objects.create(billing_record=record, line_item=line, event_type="FIELD_CORRECTION",
                                  field_name="product", old_value="DIESEL", new_value="ULSD")
        HumanDecision.objects.create(billing_record=record, decision="REJECT", previous_status="NEEDS_REVIEW",
                                     resulting_status="REJECTED", feedback_status="FAILED")
        latest_decision = HumanDecision.objects.create(
            billing_record=record, decision="REJECT", previous_status="NEEDS_REVIEW", resulting_status="REJECTED",
            feedback_status="SENT", feedback_sent_at=timezone.now(),
            feedback_metadata={"attempts": 2, "retryable": False, "payload": {"recordId": str(record.pk)}},
        )
        return record, latest_job, latest_decision

    def test_list_query_count_stays_constant_as_records_grow(self):
        self.add_record(0)
        with self.assertNumQueries(5):
            self.assertEqual(len(self.repository.list_records()), 1)
        for i in range(1, 20):
            self.add_record(i)
        with self.assertNumQueries(5):
            result = self.repository.list_records()
        self.assertEqual(len(result), 20)
        self.assertTrue(all(r["lineItems"][0]["product"]["isCorrected"] for r in result))
        self.assertTrue(all(r["feedback"]["status"] == "SENT" for r in result))
        self.assertTrue(all(r["ocrJob"]["status"] == "COMPLETED" for r in result))

    def test_batched_read_matches_legacy_serialization_and_latest_related_records(self):
        record, job, decision = self.add_record(0)
        legacy = self.repository._to_dict(BillingRecord.objects.get(pk=record.pk))
        with self.assertNumQueries(5):
            batched = self.repository.get_by_id(str(record.pk))
        self.assertEqual(batched, legacy)
        self.assertEqual(batched["ocrJob"]["jobId"], str(job.pk))
        self.assertEqual(batched["feedback"]["humanDecisionId"], str(decision.pk))
        self.assertEqual(batched["lineItems"][0]["product"]["rawValue"], "DIESEL")
        self.assertEqual(batched["lineItems"][0]["product"]["confidence"], 0.99)
        with CaptureQueriesContext(connection) as queries:
            self.repository.list_records()
        job_sql = " ".join(q["sql"] for q in queries)
        self.assertNotIn('"raw_result"', job_sql)
        self.assertNotIn('"bounding_box"', job_sql)

    def test_record_without_job_or_decision_keeps_null_summaries(self):
        record = BillingRecord.objects.create(status="UPLOADED")
        result = self.repository.get_by_id(str(record.pk))
        self.assertIsNone(result["ocrJob"])
        self.assertIsNone(result["feedback"])
        self.assertEqual(result["lineItems"], [])


class FeedbackClaimPerformanceTests(TestCase):
    def setUp(self):
        self.record = BillingRecord.objects.create(status="REJECTED")
        self.worker = FeedbackDeliveryService()

    def decision(self, metadata):
        return HumanDecision.objects.create(
            billing_record=self.record, decision="REJECT", previous_status="NEEDS_REVIEW", resulting_status="REJECTED",
            feedback_status="PENDING", feedback_metadata={"payload": {"recordId": str(self.record.pk)}, **metadata},
        )

    def test_due_filter_and_limit_exclude_future_leased_and_rejected_jobs_in_sql(self):
        future = (timezone.now() + timedelta(hours=1)).timestamp()
        for _ in range(30):
            self.decision({"retryable": True, "nextAttemptAt": future})
        self.decision({"retryable": True, "leaseUntil": future})
        self.decision({"retryable": False})
        due = self.decision({"retryable": True})
        with CaptureQueriesContext(connection) as queries:
            claim = self.worker.claim()
        self.assertEqual(claim[0], due.pk)
        selects = [q["sql"] for q in queries if q["sql"].lstrip().upper().startswith("SELECT")]
        self.assertEqual(len(selects), 1)
        self.assertIn("LIMIT 1", selects[0])
        self.assertIn("nextAttemptAt", selects[0])
        self.assertIn("leaseUntil", selects[0])
        self.assertIsNone(self.worker.claim())
        due.refresh_from_db()
        self.assertEqual(due.feedback_metadata["attempts"], 1)

    def test_legacy_snapshot_without_scheduling_keys_is_claimable(self):
        decision = self.decision({})
        self.assertEqual(self.worker.claim()[0], decision.pk)

    def test_targeted_claim_does_not_process_another_decision(self):
        future = (timezone.now() + timedelta(hours=1)).timestamp()
        later = self.decision({"nextAttemptAt": future})
        ready = self.decision({"retryable": True})
        self.assertIsNone(self.worker.claim(later.pk))
        self.assertEqual(self.worker.claim(ready.pk)[0], ready.pk)
