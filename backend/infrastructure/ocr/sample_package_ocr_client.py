import hashlib
import json
from pathlib import Path


class SamplePackageOCRClient:
    MODEL_ID = "ministral_14b_4bit"

    def __init__(self, package_root=None):
        if package_root is None:
            package_root = (
                Path(__file__).resolve().parent
                / "sample_package"
            )

        self.package_root = Path(package_root)

        manifest_path = (
            self.package_root
            / "package_manifest.json"
        )

        with manifest_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            self.manifest = json.load(file)

        self.samples_by_hash = {}

        for sample in self.manifest.get(
            "samples",
            [],
        ):
            if sample.get("variant") != "original":
                continue

            source_hash = sample.get(
                "source_file_sha256"
            )

            if not source_hash:
                continue

            self.samples_by_hash[source_hash] = sample

    def submit_document(
        self,
        *,
        document_id: str,
        file_bytes: bytes,
        filename: str,
    ) -> dict:
        file_hash = hashlib.sha256(
            file_bytes
        ).hexdigest()

        sample = self.samples_by_hash.get(
            file_hash
        )

        if sample is None:
            raise ValueError(
                "Uploaded document does not match "
                "any bundled OCR sample."
            )

        extraction_file = (
            self._find_primary_extraction(
                sample
            )
        )

        extraction_path = (
            self.package_root
            / "extractions"
            / f"{sample['sample_id']}.json"
        )

        if not extraction_path.exists():
            raise FileNotFoundError(
                f"OCR extraction file not found: "
                f"{extraction_path}"
            )

        with extraction_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            extraction = json.load(file)

        return {
            "extraction": extraction,
            "metadata": {
                "documentId": document_id,
                "filename": filename,
                "sampleId": sample["sample_id"],
                "modelId": self.MODEL_ID,
                "sourceSha256": file_hash,
                "sourceExtraction": extraction_file,
            },
        }

    def get_job(self, job_id: str) -> dict:
        raise NotImplementedError(
            "SamplePackageOCRClient returns "
            "synchronous OCR results."
        )

    def _find_primary_extraction(
        self,
        sample,
    ):
        for model in sample.get(
            "models",
            [],
        ):
            if (
                model.get("model_id")
                == self.MODEL_ID
                and model.get("repeat") == 1
            ):
                return model.get(
                    "extracted_json"
                )

        raise ValueError(
            f"No {self.MODEL_ID} extraction "
            f"found for {sample['sample_id']}."
        )
