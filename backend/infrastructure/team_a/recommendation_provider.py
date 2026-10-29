from abc import ABC, abstractmethod


class RecommendationProvider(ABC):

    @abstractmethod
    def evaluate(self, record):
        pass