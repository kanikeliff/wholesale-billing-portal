import os

from infrastructure.team_a.client import TeamAClient
from infrastructure.team_a.mock_team_a_adapter import MockTeamAAdapter
from infrastructure.team_a.team_a_adapter import TeamAAdapter


def build_recommendation_provider():
    use_mock = (
        os.getenv("USE_MOCK_TEAM_A", "true").lower()
        == "true"
    )

    if use_mock:
        return MockTeamAAdapter()

    base_url = os.getenv("TEAM_A_BASE_URL")
    api_key = os.getenv("TEAM_A_API_KEY")
    timeout = int(
        os.getenv("TEAM_A_TIMEOUT", "10")
    )

    if not base_url:
        raise RuntimeError(
            "TEAM_A_BASE_URL is required when "
            "USE_MOCK_TEAM_A=false."
        )

    if not api_key:
        raise RuntimeError(
            "TEAM_A_API_KEY is required when "
            "USE_MOCK_TEAM_A=false."
        )

    client = TeamAClient(
        base_url=base_url,
        api_key=api_key,
        timeout=timeout,
    )

    return TeamAAdapter(
        client=client,
    )
