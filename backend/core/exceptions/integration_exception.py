class IntegrationException(Exception):
    def __init__(
        self,
        code,
        message,
        *,
        details=None,
        status_code=None,
        retryable=False,
    ):
        super().__init__(message)

        self.code = code
        self.message = message
        self.details = details
        self.status_code = status_code
        self.retryable = retryable

    def to_dict(self):
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }
