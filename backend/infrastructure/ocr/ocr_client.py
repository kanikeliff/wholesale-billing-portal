from abc import ABC, abstractmethod


class OCRClient(ABC):

    @abstractmethod
    def submit_document(
        self,
        *,
        document_id: str,
        file_bytes: bytes,
        filename: str,
    ) -> dict:
        raise NotImplementedError

    @abstractmethod
    def get_job(self, job_id: str) -> dict:
        raise NotImplementedError
