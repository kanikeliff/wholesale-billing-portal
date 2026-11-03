from infrastructure.team_a.recommendation_provider import (
    RecommendationProvider,
)
from infrastructure.team_a.team_a_mapper import TeamAMapper
from infrastructure.team_a.contract_validator import TeamAContractValidator
from infrastructure.team_a.exceptions import TeamAContractError
from core.exceptions.integration_exception import IntegrationException


class TeamAAdapter(RecommendationProvider):

    def __init__(self, client, mapper=None):
        self.client = client
        self.mapper = mapper or TeamAMapper()

    def evaluate(self, record):
        payload = self.mapper.to_evaluation_request(record)

        response = self.client.evaluate(payload)

        recommendation = self.mapper.from_evaluation_response(
            response,
            expected_record_id=payload["recordId"],
        )
        try:
            TeamAContractValidator().validate_evaluate_response(
                recommendation, request_payload=payload,
            )
        except TeamAContractError as error:
            raise IntegrationException(
                "TEAM_A_INVALID_RESPONSE", str(error),
                status_code=502, retryable=False,
            ) from error
        return recommendation
