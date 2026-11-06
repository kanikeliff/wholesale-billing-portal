from io import StringIO
from unittest.mock import Mock, patch

from django.core.management import call_command, CommandError
from django.db import OperationalError
from django.test import SimpleTestCase


class FeedbackWorkerCommandTests(SimpleTestCase):
    def worker(self):
        return patch("apps.persistence.management.commands.run_feedback_worker.FeedbackDeliveryService")

    def test_database_outage_does_not_kill_continuous_worker(self):
        output, errors = StringIO(), StringIO()
        with self.worker() as service, patch(
            "apps.persistence.management.commands.run_feedback_worker.time.sleep"
        ) as sleep:
            service.return_value.process_next.side_effect = [
                OperationalError("private database connection details"), None, KeyboardInterrupt(),
            ]
            call_command("run_feedback_worker", interval=1, stdout=output, stderr=errors)
        self.assertIn("Feedback worker started", output.getvalue())
        self.assertIn("retrying", errors.getvalue())
        self.assertNotIn("private", errors.getvalue())
        self.assertEqual(service.return_value.process_next.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_once_reports_database_failure_for_operator(self):
        with self.worker() as service:
            service.return_value.process_next.side_effect = OperationalError("private details")
            with self.assertRaisesMessage(CommandError, "Feedback database temporarily unavailable"):
                call_command("run_feedback_worker", once=True, stdout=StringIO())

    def test_mock_or_missing_configuration_does_not_claim_delivery(self):
        with self.worker() as service:
            service.return_value._client.side_effect = RuntimeError("Live Team A feedback is not configured.")
            with self.assertRaises(CommandError):
                call_command("run_feedback_worker", once=True)
            service.return_value.process_next.assert_not_called()
