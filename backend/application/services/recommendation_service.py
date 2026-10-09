class RecommendationService:

    def __init__(self, recommendation_provider):
        self.recommendation_provider = recommendation_provider

    def evaluate_record(self, record):
        if record is None:
            raise ValueError("Billing record is required.")

        return self.recommendation_provider.evaluate(record)