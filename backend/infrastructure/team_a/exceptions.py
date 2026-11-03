from core.exceptions.integration_exception import IntegrationException


class TeamAIntegrationError(IntegrationException):
    def __init__(self, message, *, code="TEAM_A_ERROR", details=None,
                 status_code=502, retryable=False):
        super().__init__(code, message, details=details,
                         status_code=status_code, retryable=retryable)


class TeamAContractError(TeamAIntegrationError):
    pass


class TeamAUnavailableError(TeamAIntegrationError):
    def __init__(self, message):
        super().__init__(message, code="TEAM_A_UNAVAILABLE",
                         status_code=503, retryable=True)
