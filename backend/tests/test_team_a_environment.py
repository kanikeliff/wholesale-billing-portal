import os
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.test import SimpleTestCase

from config.local_environment import load_team_a_environment
from tools.configure_team_a import BASE_URL, save_configuration


class TeamALocalEnvironmentTests(SimpleTestCase):
    def test_secure_configuration_round_trip_preserves_other_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("# unrelated setting\nKEEP_LOCAL=value\nTEAM_A_TIMEOUT=10\n")
            # Dummy test input, never an actual credential.
            save_configuration(path, "unit-test-placeholder")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertIn("KEEP_LOCAL=value", path.read_text())
            with patch.dict(os.environ, {}, clear=True):
                load_team_a_environment(path)
                self.assertEqual(os.environ["TEAM_A_BASE_URL"], BASE_URL)
                self.assertEqual(os.environ["USE_MOCK_TEAM_A"], "false")
                self.assertEqual(os.environ["TEAM_A_TIMEOUT"], "30")
                self.assertNotIn("KEEP_LOCAL", os.environ)

    def test_exports_override_local_values_without_shell_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("USE_MOCK_TEAM_A=false\nTEAM_A_BASE_URL='$(not-executed)'\n")
            with patch.dict(os.environ, {"USE_MOCK_TEAM_A": "true"}, clear=True):
                load_team_a_environment(path)
                self.assertEqual(os.environ["USE_MOCK_TEAM_A"], "true")
                self.assertEqual(os.environ["TEAM_A_BASE_URL"], "$(not-executed)")

    def test_malformed_configuration_does_not_echo_value(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("TEAM_A_API_KEY='unterminated\n")
            with self.assertRaisesRegex(RuntimeError, "Invalid local configuration for TEAM_A_API_KEY"):
                load_team_a_environment(path)

    def test_missing_file_is_optional(self):
        with tempfile.TemporaryDirectory() as directory:
            load_team_a_environment(Path(directory) / ".env")
