class TeamAIntegrationError(Exception):
    pass


class TeamAContractError(TeamAIntegrationError):
    pass


class TeamAUnavailableError(TeamAIntegrationError):
    pass
