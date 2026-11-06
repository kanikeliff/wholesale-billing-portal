"""Read-only evaluation of immutable OCR evidence against independent labels."""
from collections import defaultdict
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
import statistics
import unicodedata

from apps.persistence.models import Document, ExtractedField, OCRJob

HEADERS = {"bolNumber", "contractLifting", "origin", "supplier", "carrier", "transactionDate", "destination"}
LINES = {"product", "e3StockId", "netGallons", "grossGallons"}


def canonical(value, field):
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if field in {"netGallons", "grossGallons"}:
        if isinstance(value, bool):
            raise ValueError("Boolean values are not gallon labels.")
        try:
            number = Decimal(str(value))
        except InvalidOperation:
            raise ValueError("Gallon values must be numeric.") from None
        if not number.is_finite():
            raise ValueError("Gallon values must be finite.")
        return number
    return " ".join(unicodedata.normalize("NFKC", str(value)).strip().casefold().split())


def score_manifest(manifest, *, tuning_manifest=None, baseline=None):
    if not isinstance(manifest, dict):
        raise ValueError("Manifest must be a JSON object.")
    if manifest.get("schemaVersion") != 1 or manifest.get("split") not in {"baseline", "unseen"}:
        raise ValueError("Use schemaVersion=1 and split=baseline or unseen.")
    documents = manifest.get("documents")
    if not isinstance(documents, list) or not documents:
        raise ValueError("At least one independently labeled document is required.")
    tuning = {d["sourceSHA256"] for d in (tuning_manifest or {}).get("documents", [])}
    seen = set(); dataset = []; rows = []; durations = []; per_field = defaultdict(lambda: {"correct": 0, "total": 0})
    correct = total = scored = 0; squared_error = 0.0
    for entry in documents:
        checksum = entry.get("sourceSHA256", "")
        if not isinstance(checksum, str) or not re.fullmatch(r"[a-f0-9]{64}", checksum):
            raise ValueError("Each document needs its lowercase sourceSHA256.")
        if checksum in seen:
            raise ValueError("Duplicate source document in evaluation manifest.")
        if checksum in tuning:
            raise ValueError("Evaluation source overlaps the tuning manifest.")
        seen.add(checksum)
        document = Document.objects.get(pk=entry["documentId"])
        if document.checksum_sha256 != checksum:
            raise ValueError("Document checksum does not match its stored source.")
        job = OCRJob.objects.filter(document=document).only("status", "started_at", "completed_at").order_by("-created_at", "-pk").first()
        if job is None or job.status != "COMPLETED":
            raise ValueError("Document latest OCR job is not completed.")
        expected = entry.get("expected", {})
        labels = {(None, name): value for name, value in expected.get("fields", {}).items()}
        if not set(expected.get("fields", {})).issubset(HEADERS):
            raise ValueError("Unknown header label.")
        line_numbers = set()
        for line in expected.get("lineItems", []):
            number = line.get("lineNumber")
            if type(number) is not int or number < 1 or number in line_numbers:
                raise ValueError("Expected line numbers must be positive and unique.")
            line_numbers.add(number)
            if not set(line).issubset(LINES | {"lineNumber"}):
                raise ValueError("Unknown line-item label.")
            labels.update({(number, k): v for k, v in line.items() if k != "lineNumber"})
        if not labels:
            raise ValueError("Document contains no labeled fields.")
        evidence = {}
        for field in ExtractedField.objects.filter(document=document).select_related("line_item").order_by("created_at", "pk"):
            evidence[(field.line_item.line_number if field.line_item_id else None, field.field_name)] = field
        if not evidence:
            raise ValueError("No immutable OCR evidence is available for this document.")
        doc_correct = 0
        for key, truth in labels.items():
            field = evidence.get(key)
            predicted = field.normalized_value if field else None
            matches = canonical(predicted, key[1]) == canonical(truth, key[1])
            correct += int(matches); total += 1; doc_correct += int(matches)
            stats = per_field[key[1]]; stats["total"] += 1; stats["correct"] += int(matches)
            if field is not None and field.confidence is not None:
                scored += 1
                squared_error += (float(field.confidence) - int(matches)) ** 2
        if job.started_at and job.completed_at:
            duration = (job.completed_at - job.started_at).total_seconds()
            if duration < 0:
                raise ValueError("OCR job completion precedes its start.")
            durations.append(duration)
        rows.append({"documentId": str(document.pk), "ocrJobId": str(job.pk), "sourceSHA256": checksum,
                     "labeledFields": len(labels), "correctFields": doc_correct})
        dataset.append({"sourceSHA256": checksum, "expected": expected})
    digest = hashlib.sha256(json.dumps(sorted(dataset, key=lambda r: r["sourceSHA256"]), sort_keys=True).encode()).hexdigest()
    report = {"schemaVersion": 1, "datasetDigest": digest, "split": manifest["split"],
              "holdoutCheck": "no overlap with supplied tuning manifest" if tuning_manifest is not None else "unseen status declared, not independently verified",
              "normalization": "NFKC/casefold/whitespace for text; exact Decimal for gallons; null equals blank; leading zeros retained",
              "documents": rows, "labeledFields": total, "correctFields": correct,
              "fieldAccuracy": correct / total,
              "perField": {k: dict(v, accuracy=v["correct"] / v["total"]) for k, v in sorted(per_field.items())},
              "latency": {"measuredDocuments": len(durations), "medianProcessingSeconds": statistics.median(durations) if durations else None},
              "certainty": {"scoredFields": scored, "brierScore": squared_error / scored if scored else None, "calibrated": False}}
    if baseline is not None:
        if baseline.get("schemaVersion") != 1 or baseline.get("datasetDigest") != digest:
            raise ValueError("Baseline comparison requires identical source documents and labels.")
        report["comparison"] = {"baselineFieldAccuracy": baseline["fieldAccuracy"],
                                "accuracyDeltaPercentagePoints": (report["fieldAccuracy"] - baseline["fieldAccuracy"]) * 100}
    return report
