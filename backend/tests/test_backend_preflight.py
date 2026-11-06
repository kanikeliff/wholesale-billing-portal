from io import StringIO
import json
from unittest.mock import patch
from django.core.management import call_command, CommandError
from django.test import TestCase


class BackendPreflightTests(TestCase):
    def test_configured_sample_dependencies_report_no_secrets(self):
        output = StringIO()
        with patch.dict("os.environ", {"OCR_PROVIDER": "sample", "USE_MOCK_TEAM_A": "false",
                                       "TEAM_A_BASE_URL": "https://team-a.test", "TEAM_A_API_KEY": "private-test-key"}):
            call_command("backend_preflight", strict=True, stdout=output)
        report = json.loads(output.getvalue())
        self.assertTrue(report["ready"])
        self.assertEqual(report["feedback"]["workerLiveness"], "not checked")
        self.assertNotIn("private-test-key", output.getvalue())

    def test_strict_live_requirement_does_not_accept_sample_mode(self):
        output = StringIO()
        with patch.dict("os.environ", {"OCR_PROVIDER": "sample"}):
            with self.assertRaises(CommandError):
                call_command("backend_preflight", strict=True, require_live_ocr=True, stdout=output)
        self.assertFalse(json.loads(output.getvalue())["ocr"]["ready"])

    def test_database_failure_is_sanitized(self):
        output = StringIO()
        with patch("apps.persistence.management.commands.backend_preflight.connection.ensure_connection",
                   side_effect=RuntimeError("database-password-value")):
            call_command("backend_preflight", stdout=output)
        self.assertFalse(json.loads(output.getvalue())["database"]["ready"])
        self.assertNotIn("database-password-value", output.getvalue())
