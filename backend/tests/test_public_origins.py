import os
from unittest.mock import patch

from django.test import SimpleTestCase

from config.public_origins import public_portal_origins


class PublicPortalOriginsTests(SimpleTestCase):
    @patch.dict(os.environ, {"PORTAL_PUBLIC_ORIGINS": "https://portal.example.test/,http://localhost:5173"})
    def test_explicit_origins_are_supported(self):
        self.assertEqual(public_portal_origins(), ["https://portal.example.test", "http://localhost:5173"])

    def test_wildcards_paths_and_credentials_are_rejected(self):
        for value in ("https://*.example.test", "https://portal.example.test/path", "https://user:password@example.test", "file:///tmp/file"):
            with patch.dict(os.environ, {"PORTAL_PUBLIC_ORIGINS": value}):
                with self.assertRaises(ValueError):
                    public_portal_origins()

    @patch.dict(os.environ, {"PORTAL_PUBLIC_ORIGINS": ""})
    def test_public_origin_is_opt_in(self):
        self.assertEqual(public_portal_origins(), [])
