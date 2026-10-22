from infrastructure.team_a.recommendation_provider import (
    RecommendationProvider,
)
from infrastructure.team_a.team_a_mapper import TeamAMapper


class TeamAAdapter(RecommendationProvider):

    def __init__(self, client, mapper=None):
        self.client = client
        self.mapper = mapper or TeamAMapper()

    def evaluate(self, record):
        payload = self.mapper.to_evaluation_request(record)

        response = self.client.evaluate(payload)

        return self.mapper.from_evaluation_response(
            response,
            expected_record_id=payload["recordId"],
        )
