import os
from unittest.mock import patch

from django.test import SimpleTestCase

from infrastructure.team_a.mock_team_a_adapter import (
    MockTeamAAdapter,
)
from infrastructure.team_a.provider_factory import (
    build_recommendation_provider,
)


class TeamAProviderFactoryTests(SimpleTestCase):

    @patch.dict(
        os.environ,
        {
            "USE_MOCK_TEAM_A": "true",
        },
        clear=True,
    )
    def test_builds_mock_provider(self):
        provider = build_recommendation_provider()

        self.assertIsInstance(
            provider,
            MockTeamAAdapter,
        )

    @patch.dict(
        os.environ,
        {
            "USE_MOCK_TEAM_A": "false",
        },
        clear=True,
    )
    def test_real_provider_requires_base_url(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "TEAM_A_BASE_URL",
        ):
            build_recommendation_provider()

    @patch.dict(
        os.environ,
        {
            "USE_MOCK_TEAM_A": "false",
            "TEAM_A_BASE_URL":
                "http://127.0.0.1:8001",
        },
        clear=True,
    )
    def test_real_provider_requires_api_key(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "TEAM_A_API_KEY",
        ):
            build_recommendation_provider()
