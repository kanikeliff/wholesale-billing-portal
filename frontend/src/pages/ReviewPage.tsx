import "./ReviewPage.css";
import BolPdfViewer from "../components/BolPdfViewer";
import { validateBillingRecord } from "../api/validationApi";
import { evaluateBillingRecord } from "../api/recommendationApi";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  submitBillingDecision,
  type HumanDecision,
} from "../api/decisionApi";

import {
  getBillingRecord,
  type BillingRecord,
  type ExtractedField,
} from "../api/billingRecordApi";


import { updateBillingField, updateBillingLineItem } from "../api/correctionApi";

type FieldKey = keyof BillingRecord["fields"];
type DraftValues = Record<string, string>;

type ValidationIssue = {
  code: string;
  severity: string;
  field?: string;
  message: string;
  lineItemId?: string | number;
};

type ValidationResponse = {
  recordId: string;
  valid: boolean;
  blockingIssues: ValidationIssue[];
  reviewFlags: ValidationIssue[];
  nextStatus: string;
};

type EvaluationResponse = {
  recordId: string;
  status: string;
  pending: boolean;
  recommendation: {
    recordId?: string;
    recommendation: string;
    confidence: number | null;
    modelVersion?: string;
    rationale?: string;
    matchedTerminalLogId?: string | null;
    mappedEntities?: {
      carrierCode?: string | null;
      lineItems?: {
        lineItemId: string | number;
        e3StockId?: string | null;
        standardName?: string | null;
      }[];
    };
  } | null;
};




const shipmentFields: {
  key: FieldKey;
  label: string;
}[] = [
  { key: "bolNumber", label: "BOL Number" },
  { key: "contractLifting", label: "Contract / Lifting" },
  { key: "origin", label: "Origin" },
  { key: "supplier", label: "Supplier" },
  { key: "carrier", label: "Carrier" },
  { key: "transactionDate", label: "Transaction Date" },
  { key: "destination", label: "Destination" },
];

function toText(value: unknown): string {
  return value == null ? "" : String(value);
}

function needsReview(field: ExtractedField<unknown>) {
  return (
    field.quality === "LOW_CONFIDENCE" ||
    field.quality === "MISSING" ||
    field.quality === "UNREADABLE" ||
    field.quality === "INVALID"
  );
}

function confidenceText(field: ExtractedField<unknown>) {
  if (field.confidence == null) {
    return "Unavailable";
  }

  return `${Math.round(field.confidence * 100)}%`;
}



function createDraft(record: BillingRecord): DraftValues {
  const draft: DraftValues = {};

  shipmentFields.forEach(({ key }) => {
    draft[key] = toText(record.fields[key].normalizedValue);
  });

  record.lineItems.forEach((item) => {
    draft[`line-${item.lineItemId}-product`] =
      toText(item.product.normalizedValue);

    draft[`line-${item.lineItemId}-grossGallons`] =
      toText(item.grossGallons.normalizedValue);

    draft[`line-${item.lineItemId}-netGallons`] =
      toText(item.netGallons.normalizedValue);

    draft[`line-${item.lineItemId}-e3StockId`] =
      toText(item.e3StockId.normalizedValue);
  });

  return draft;
}

export default function ReviewPage() {
  const { id } = useParams();

  const [record, setRecord] = useState<BillingRecord | null>(
    null
  );
  const [draft, setDraft] = useState<DraftValues>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");
  const [saveError, setSaveError] = useState("");
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] =
  useState<unknown>(null);
  const [decisionReason, setDecisionReason] = useState("");
  const [submittingDecision, setSubmittingDecision] = useState(false);
  const [decisionError, setDecisionError] = useState("");
  const [decisionMessage, setDecisionMessage] = useState("");

const [validationError, setValidationError] = useState("");

const [evaluating, setEvaluating] = useState(false);

const [evaluationResult, setEvaluationResult] =
  useState<unknown>(null);

const [evaluationError, setEvaluationError] = useState("");


  useEffect(() => {
    let active = true;

    if (!id) {
      setLoading(false);
      setError("Record ID is missing.");
      return;
    }

    setLoading(true);
    setError("");
    setRecord(null);
    setDraft({});
    setSaveMessage("");
    setSaveError("");

    const loadRecord = async () => {
      try {
        // Load actual OCR data from Team B backend.
        const backendRecord = await getBillingRecord(id);

        if (!active) return;

        setRecord(backendRecord);
        setDraft(createDraft(backendRecord));
       
      } catch (backendError) {
        if (!active) return;
      
        console.error(
          "Backend billing record request failed:",
          backendError
        );
      
        setRecord(null);
        setDraft({});
          
        setError(
          backendError instanceof Error
            ? `Could not load this BOL from the backend: ${backendError.message}`
            : "Could not load this BOL from the backend."
        );
      } finally {
        if (active) setLoading(false);
      }
    };

    loadRecord();

    return () => {
      active = false;
    };
  }, [id]);

  const originalValues = useMemo(
    () => (record ? createDraft(record) : {}),
    [record]
  );

  const hasChanges = Object.keys(draft).some(
    (key) => draft[key] !== originalValues[key]
  );

const validation = validationResult as ValidationResponse | null;

const evaluation =
  evaluationResult as EvaluationResponse | null;

const teamRecommendation = evaluation?.recommendation ?? null;

const evaluationConfidence =
  teamRecommendation?.confidence == null
    ? "Unavailable"
    : `${Math.round(teamRecommendation.confidence * 100)}%`;

const recommendationLabel = (value: string) =>
  value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());


const blockingIssues = validation?.blockingIssues ?? [];
const reviewFlags = validation?.reviewFlags ?? [];

const formatValidationLabel = (value: string) =>
  value
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());


  const updateDraft = (key: string, value: string) => {
    setSaveError("");
    setSaveMessage("");
    setDraft((previous) => ({
      ...previous,
      [key]: value,
    }));
  };

  const discardChanges = () => {
    setSaveMessage("");
    setSaveError("");
    if (record) {
      setDraft(createDraft(record));
    }
  };
  const runValidation = async () => {
    if (!record || saving || validating || hasChanges) {
      return;
    }
  
    setValidating(true);
    setValidationError("");
    setValidationResult(null);
  
    try {
      const result = await validateBillingRecord(record.recordId);
      setValidationResult(result);
    } catch (err) {
      setValidationError(
        err instanceof Error ? err.message : "Validation failed."
      );
    } finally {
      setValidating(false);
    }
  };

const refreshRecommendation = async () => {
  if (
    !record ||
    saving ||
    evaluating ||
    validating ||
    hasChanges
  ) {
    return;
  }

  setEvaluating(true);
  setEvaluationError("");
  setEvaluationResult(null);

  try {
    const result = await evaluateBillingRecord(record.recordId);
    setEvaluationResult(result);

    const updatedRecord = await getBillingRecord(record.recordId);
    setRecord(updatedRecord);
  } catch (err) {
    setEvaluationError(
      err instanceof Error
        ? err.message
        : "Recommendation evaluation failed."
    );
  } finally {
    setEvaluating(false);
  }
};


  // Only submit changed fields. Do not silently save mock/fallback data.
  const saveChanges = async () => {
    if (!record || saving || !hasChanges) return;
    const original = createDraft(record);
    const modifiedKeys = Object.keys(draft).filter(
      (key) => draft[key] !== original[key]
    );
    const lineFields = ["product", "grossGallons", "netGallons", "e3StockId"] as const;
    type PendingChange = {
      key: string;
      kind: "field" | "line";
      fieldName: string;
      lineItemId?: string | number;
      value: string | number | null;
    };
    const pending: PendingChange[] = [];

    for (const key of modifiedKeys) {
      const shipment = shipmentFields.find((entry) => entry.key === key);
      if (shipment) {
        pending.push({
          key,
          kind: "field",
          fieldName: shipment.key,
          value: draft[key].trim() || null,
        });
        continue;
      }
      const line = record.lineItems.find((item) =>
        lineFields.some((name) => `line-${item.lineItemId}-${name}` === key)
      );
      const lineName = lineFields.find(
        (name) => line && `line-${line.lineItemId}-${name}` === key
      );
      if (!line || !lineName) {
        setSaveError(`Unrecognized correction field: ${key}`);
        return;
      }
      const raw = draft[key].trim();
      let value: string | number | null = raw || null;
      if (lineName === "grossGallons" || lineName === "netGallons") {
        if (raw && (!Number.isFinite(Number(raw)) || Number(raw) < 0)) {
          setSaveError(`${lineName} must be a non-negative number.`);
          return;
        }
        value = raw ? Number(raw) : null;
      }
      pending.push({ key, kind: "line", fieldName: lineName, lineItemId: line.lineItemId, value });
    }

    setSaving(true);
    setSaveError("");
    setSaveMessage("");
    const completed = new Set<string>();
    let failure = "";
    const reviewedBy = "user_001"; // Demo identity; replace with authenticated user ID.

    for (const change of pending) {
      try {
        if (change.kind === "field") {
          await updateBillingField(record.recordId, change.fieldName, change.value, reviewedBy);
        } else {
          await updateBillingLineItem(record.recordId, change.lineItemId!, change.fieldName, change.value, reviewedBy);
        }
        completed.add(change.key);
      } catch (err) {
        failure = err instanceof Error ? err.message : "Unknown API error";
        break;
      }
    }

    // Verify backend values before restoring unsaved edits.
    try {
      const refreshed = await getBillingRecord(record.recordId);
      const actualValues = createDraft(refreshed);

      const unverifiedEdits = modifiedKeys.filter(
        (key) =>
          !completed.has(key) ||
          actualValues[key] !== draft[key]
      );

      const unpersisted = [...completed].filter(
        (key) => actualValues[key] !== draft[key]
      );

      const nextDraft = { ...actualValues };

      for (const key of unverifiedEdits) {
        nextDraft[key] = draft[key];
      }

      setRecord(refreshed);
      setDraft(nextDraft);

      if (unpersisted.length > 0) {
        setSaveError(
          `The API accepted ${completed.size} correction(s), but ${unpersisted.length} value(s) were not confirmed by the refreshed record.`
        );
      } else if (!failure && completed.size > 0) {
        setSaveMessage(
          `${completed.size} correction(s) saved and confirmed by the backend API.`
        );
      }
    } catch (refreshErr) {
      const detail =
        refreshErr instanceof Error
          ? refreshErr.message
          : "Unknown refresh error";

      setSaveError(
        `Correction requests completed: ${completed.size}/${pending.length}, but refreshing the record failed: ${detail}. Check backend state before retrying.`
      );
    } finally {
      setSaving(false);
    }

    if (failure) {
      setSaveError(`Saved ${completed.size}/${pending.length} correction(s). Next request failed: ${failure}. Remaining edits are kept on screen.`);
    }
  };

   
const allowedDecisions: Record<string, HumanDecision[]> = {
  UPLOADED: ["EXCEPTION"],
  OCR_PROCESSING: ["EXCEPTION"],
  OCR_COMPLETE: [],
  NEEDS_REVIEW: ["REJECT", "EXCEPTION"],
  RECOMMENDATION_PENDING: ["EXCEPTION"],
  RECOMMENDATION_READY: [
    "APPROVE",
    "REJECT",
    "EXCEPTION",
  ],
};

const availableDecisions =
  record ? allowedDecisions[record.status] ?? [] : [];

const handleDecision = async (decision: HumanDecision) => {
  if (
    !record ||
    submittingDecision ||
    saving ||
    validating ||
    evaluating ||
    hasChanges ||
    !availableDecisions.includes(decision)
  ) {
    return;
  }

  const reason = decisionReason.trim();

  if (!reason) {
    setDecisionError("Please enter a decision reason.");
    return;
  }

  const confirmed = window.confirm(
    `Submit ${decision} for BOL ${
      record.fields.bolNumber.normalizedValue ?? record.recordId
    }?\n\nReason: ${reason}\n\nThis action updates the backend record.`
  );

  if (!confirmed) return;

  setSubmittingDecision(true);
  setDecisionError("");
  setDecisionMessage("");

  try {
    const result = await submitBillingDecision(
      record.recordId,
      decision,
      reason
    );

    const updatedRecord = await getBillingRecord(record.recordId);

    setRecord(updatedRecord);
    setDraft(createDraft(updatedRecord));
    setValidationResult(null);
    setEvaluationResult(null);
    setDecisionReason("");

    setDecisionMessage(
      `${result.decision} submitted. Backend status: ${updatedRecord.status}`
    );
  } catch (err) {
    setDecisionError(
      err instanceof Error
        ? err.message
        : "Unable to submit the decision."
    );
  } finally {
    setSubmittingDecision(false);
  }
};


  const renderField = (
    key: string,
    label: string,
    field: ExtractedField<string | number | null>
  ) => {
    const warning = needsReview(field);

    return (
      <div
        className={`review-field ${warning ? "warning" : ""}`}
        key={key}
      >
        <label className="review-field-label" htmlFor={key}>
          {label}
        </label>

        <input
          id={key}
          className="review-field-input"
          type="text"
          value={draft[key] ?? ""}
          onChange={(event) =>
            updateDraft(key, event.target.value)
          }
          disabled={saving}
        />

        <div className="review-field-meta">
          <span>OCR Confidence</span>

          <span
            className={`review-confidence ${
              field.confidence == null
                ? "unavailable"
                : warning
                ? "low"
                : ""
            }`}
          >
            {confidenceText(field)}
          </span>
        </div>

        <p className="review-field-raw">
          Original OCR: {field.rawValue ?? "Not available"}
        </p>

        {warning && (
          <p className="review-warning-text">
            Review required: {(field.quality ?? "UNKNOWN").replace(/_/g, " ")}
          </p>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <main className="review-page">
        <p>Loading billing record...</p>
      </main>
    );
  }

  if (error || !record) {
    return (
      <main className="review-page">
        <Link to="/dashboard" className="review-back-link">
          ← Back to Dashboard
        </Link>

        <h1>Unable to Load Record</h1>
        <p>{error || "Billing record not found."}</p>
      </main>
    );
  }

  
  const backendBaseUrl = "http://127.0.0.1:8000";

  const documentUrl = record.document?.documentUrl
    ? `${backendBaseUrl}${record.document.documentUrl}`
    : "";

  const documentFileName =
    record.document?.originalFilename ||
    "Original BOL unavailable";


 


  const isPdf = /\.pdf(?:[?#]|$)/i.test(documentUrl);
  const recommendation = record.recommendation;

  return (
    <main className="review-page">
      {/* PAGE HEADER */}

      <header className="review-header">
        <div>
          <h1>BOL Review Workspace</h1>
          <p className="review-subtitle">
            Verify OCR results against the original document.
          </p>
        </div>

        <Link to="/dashboard" className="review-back-link">
          ← Back to Dashboard
        </Link>
      </header>

      <div className="review-record-info" style={{
        marginBottom: "20px"
      }}>
        <span className="review-record-id">
          Record: {record.recordId}
        </span>

        <span className="review-status">
          {record.status.replace(/_/g, " ")}
        </span>

        <span className="review-record-id">
        {documentFileName}
        </span>
      </div>



      {/* THREE-PANEL WORKSPACE */}

      <div className="review-workspace">

       
{/* LEFT: DOCUMENT QUEUE */}

<aside className="review-panel">
  <div className="review-panel-header">
    <h2>Document Queue</h2>
    <p className="review-panel-subtitle">
      Current PostgreSQL record
    </p>
  </div>

  <div className="review-panel-body">
    <div className="review-queue">
      <Link
        className="review-queue-item active"
        to={`/records/${encodeURIComponent(record.recordId)}/review`}
      >
        <div className="review-queue-title">
          {record.fields?.bolNumber?.normalizedValue
            ? `BOL ${record.fields.bolNumber.normalizedValue}`
            : record.recordId}
        </div>

        <div className="review-queue-details">
          Record ID: {record.recordId}
        </div>

        <div className="review-queue-details">
          {record.status.replace(/_/g, " ")}
        </div>

        <div className="review-queue-details">
          Current document
        </div>
      </Link>
    </div>
  </div>
</aside>

{/* CENTER: ORIGINAL BOL */}


        <section className="review-panel">
          <div className="review-panel-header">
            <h2>Original BOL</h2>
            <p className="review-panel-subtitle">
            {documentFileName}
            </p>
          </div>

          <div className="review-document-container">
            {documentUrl ? (
              isPdf ? (
                <BolPdfViewer fileUrl={documentUrl} />

              ) : (
                <img
                  src={documentUrl}
                  alt={`Original BOL ${record.recordId}`}
                  style={{
                    width: "100%",
                    height: "auto",
                    background: "#fff",
                  }}
                />
              )
            ) : (
              <p>
                No source document URL is available
                for this record.
              </p>
            )}
          </div>

          {documentUrl && (
            <div className="review-document-actions">
              <a
                href={documentUrl}
                target="_blank"
                rel="noreferrer"
                className="review-document-link"
              >
                Open Original Document ↗
              </a>
            </div>
          )}
        </section>

        {/* RIGHT: OCR REVIEW */}

        <section className="review-panel">
          <div className="review-panel-header">
            <h2>Review & Verify</h2>
            <p className="review-panel-subtitle">
              Extracted billing information
            </p>
          </div>

          <div className="review-panel-body">

            <h3>Shipment Information</h3>

            <div className="review-fields">
              {shipmentFields.map(({ key, label }) =>
                renderField(
                  key,
                  label,
                  record.fields[key]
                )
              )}
            </div>

            {/* PRODUCT LINE ITEMS */}

            <h3 style={{ marginTop: "25px" }}>
              Product Line Items
            </h3>

            {record.lineItems.length === 0 && (
              <p>No product line items found.</p>
            )}

            {record.lineItems.map((item) => (
              <div
                key={item.lineItemId}
                className="review-line-item"
              >
                <h3>Line Item {item.lineItemId}</h3>

                <div className="review-fields">
                  {renderField(
                    `line-${item.lineItemId}-product`,
                    "Product",
                    item.product
                  )}

                  {renderField(
                    `line-${item.lineItemId}-grossGallons`,
                    "Gross Gallons",
                    item.grossGallons
                  )}

                  {renderField(
                    `line-${item.lineItemId}-netGallons`,
                    "Net Gallons",
                    item.netGallons
                  )}

                  {renderField(
                    `line-${item.lineItemId}-e3StockId`,
                    "E3 Stock ID",
                    item.e3StockId
                  )}
                </div>
              </div>
            ))}

            {/* TEAM A RECOMMENDATION */}

            <div className="review-recommendation">
              <h3>Team A Recommendation</h3>

              {recommendation ? (
                <>
                  <p>
                    <strong>Recommendation:</strong>{" "}
                    {recommendation.recommendation}
                  </p>

                  <p>
                    <strong>Confidence:</strong>{" "}
                    {recommendation.confidence == null
                      ? "Unavailable"
                      : `${Math.round(
                          recommendation.confidence * 100
                        )}%`}
                  </p>

                  <p>
                    <strong>Rationale:</strong>{" "}
                    {recommendation.rationale ||
                      "Not provided"}
                  </p>

                  <p>
                    <strong>Matched Terminal Log:</strong>{" "}
                    {recommendation.matchedTerminalLogId ??
                      "Not available"}
                  </p>

                  {recommendation.mappedEntities && (
                    <>
                      <p>
                        <strong>Carrier Code:</strong>{" "}
                        {recommendation.mappedEntities
                          .carrierCode ?? "Not available"}
                      </p>

                      {recommendation.mappedEntities
                        .lineItems.map((mappedItem) => (
                          <div key={mappedItem.lineItemId}>
                            <p>
                              <strong>Line:</strong>{" "}
                              {mappedItem.lineItemId}
                            </p>

                            <p>
                              <strong>E3 Stock ID:</strong>{" "}
                              {mappedItem.e3StockId ??
                                "Not available"}
                            </p>

                            <p>
                              <strong>Standard Name:</strong>{" "}
                              {mappedItem.standardName ??
                                "Not available"}
                            </p>
                          </div>
                        ))}
                    </>
                  )}

                  {recommendation.exceptionIndicators.map(
                    (exception, index) => (
                      <p
                        key={`${exception.code}-${index}`}
                        className="review-warning-text"
                      >
                        {exception.severity}:{" "}
                        {exception.message}
                      </p>
                    )
                  )}
                </>
              ) : (
                <p className="review-recommendation-note">
                  No Team A recommendation available yet.
                </p>
              )}
            </div>

            {/* REVIEW ACTIONS */}

            <div className="review-actions">
              <button
                className="review-btn review-btn-secondary"
                disabled={!hasChanges || saving}
                onClick={discardChanges}
              >
                Discard Changes
              </button>

              <button
                className="review-btn review-btn-primary"
                disabled={!hasChanges || saving}
                onClick={saveChanges}
                
              >
                {saving ? "Saving..." : "Save Changes"}
              </button>
              <button
                type="button"
                className="review-btn review-btn-secondary"
                disabled={saving || validating || hasChanges}
                onClick={runValidation}
               >
              {validating ? "Validating..." : "Validate Record"}
              </button>

            <button
            type="button"
            className="review-btn review-btn-secondary"
            disabled={
                    saving ||
            validating ||
            evaluating ||
            hasChanges
            }
            onClick={refreshRecommendation}
            >
            {evaluating ? "Refreshing..." : "Refresh Recommendation"}
            </button>

            </div>


<div
  className="review-recommendation"
  style={{ marginTop: "24px" }}
>
  <h3>Human Decision</h3>

  <p>
    <strong>Current Status:</strong>{" "}
    {record.status.replace(/_/g, " ")}
  </p>

  <label
    htmlFor="decision-reason"
    className="review-field-label"
  >
    Decision Reason
  </label>

  <textarea
    id="decision-reason"
    value={decisionReason}
    onChange={(e) => setDecisionReason(e.target.value)}
    placeholder="Enter a reason for your decision..."
    rows={3}
    disabled={submittingDecision}
    style={{
      width: "100%",
      padding: "12px",
      borderRadius: "8px",
      border: "1px solid #dce2ea",
      marginTop: "8px",
      marginBottom: "14px",
      boxSizing: "border-box",
    }}
  />

  <div className="review-actions">
    {(
      [
        ["APPROVE", "Approve"],
        ["REJECT", "Reject"],
        ["EXCEPTION", "Exception"],
      ] as const
    ).map(([decision, label]) => (
      <button
        key={decision}
        type="button"
        className="review-btn review-btn-secondary"
        disabled={
          !availableDecisions.includes(decision) ||
          submittingDecision ||
          saving ||
          validating ||
          evaluating ||
          hasChanges ||
          false
        }
        onClick={() => void handleDecision(decision)}
      >
        {submittingDecision ? "Submitting..." : label}
      </button>
    ))}
  </div>

  {decisionError && (
    <p role="alert" style={{ color: "#a21d1d" }}>
      {decisionError}
    </p>
  )}

  {decisionMessage && (
    <p role="status" style={{ color: "#166534" }}>
      {decisionMessage}
    </p>
  )}

  <p className="review-recommendation-note">
    Decisions are submitted to Team B backend.
    Reviewer identity integration is not yet complete.
  </p>
</div>


            {evaluationError && (
            <div
            className="review-message"
            role="alert"
            style={{ color: "#a21d1d" }}
            >
            Recommendation refresh failed: {evaluationError}
           </div>
)}


{evaluation && (
  <div
    className="review-message"
    style={{
      background: "#ffffff",
      border: "1px solid #dce2ea",
      borderRadius: "12px",
      padding: "20px",
      marginTop: "16px",
      color: "#1f2937",
    }}
  >
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexWrap: "wrap",
        gap: "12px",
        marginBottom: "20px",
      }}
    >
      <h3 style={{ margin: 0 }}>Team A Recommendation</h3>

      <span
        style={{
          borderRadius: "20px",
          padding: "6px 12px",
          fontWeight: 600,
          background: evaluation.pending ? "#fef3c7" : "#dcfce7",
          color: evaluation.pending ? "#92400e" : "#166534",
        }}
      >
        {evaluation.pending ? "Pending" : "Ready"}
      </span>
    </div>

    {evaluation.pending ? (
      <p>
        The recommendation is still being processed.
        Refresh again later to check the updated result.
      </p>
    ) : teamRecommendation ? (
      <>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "16px",
            flexWrap: "wrap",
            marginBottom: "20px",
          }}
        >
          <div
            style={{
              padding: "18px",
              borderRadius: "12px",
              background: "#f0fdf4",
              textAlign: "center",
              minWidth: "125px",
            }}
          >
            <div
              style={{
                color: "#166534",
                fontWeight: 700,
                fontSize: "28px",
              }}
            >
              {evaluationConfidence}
            </div>
            <div style={{ fontSize: "12px", color: "#64748b" }}>
              Confidence
            </div>
          </div>

          <div style={{ flex: 1 }}>
            <h3 style={{ margin: "0 0 8px" }}>
              {recommendationLabel(
                teamRecommendation.recommendation
              )}
            </h3>

            <p style={{ color: "#64748b", margin: 0 }}>
              {teamRecommendation.rationale ||
                "No rationale provided."}
            </p>
          </div>
        </div>

        <h4>Matching Details</h4>

        <div
          style={{
            display: "grid",
            gridTemplateColumns:
              "repeat(2, minmax(0, 1fr))",
            gap: "12px",
            marginBottom: "20px",
          }}
        >
          {[
            {
              label: "Terminal Log",
              value:
                teamRecommendation.matchedTerminalLogId,
            },
            {
              label: "Carrier Code",
              value:
                teamRecommendation.mappedEntities?.carrierCode,
            },
          ].map((item) => (
            <div
              key={item.label}
              style={{
                background: "#f8fafc",
                borderRadius: "10px",
                padding: "14px",
              }}
            >
              <div
                style={{
                  color: "#64748b",
                  fontSize: "13px",
                  marginBottom: "5px",
                }}
              >
                {item.label}
              </div>
              <strong>{item.value ?? "Not available"}</strong>
            </div>
          ))}
        </div>

        <h4>Product Mapping</h4>

        {(teamRecommendation.mappedEntities?.lineItems ?? [])
          .length > 0 ? (
          teamRecommendation.mappedEntities?.lineItems?.map(
            (item) => (
              <div
                key={item.lineItemId}
                style={{
                  background: "#f8fafc",
                  borderRadius: "10px",
                  padding: "14px",
                  marginBottom: "10px",
                }}
              >
                <strong>Line Item {item.lineItemId}</strong>
                <p style={{ margin: "8px 0 4px" }}>
                  E3 Stock ID:{" "}
                  <strong>
                    {item.e3StockId ?? "Not available"}
                  </strong>
                </p>
                <p style={{ margin: 0 }}>
                  Standard Product:{" "}
                  <strong>
                    {item.standardName ?? "Not available"}
                  </strong>
                </p>
              </div>
            )
          )
        ) : (
          <p>No product mappings available.</p>
        )}

        {teamRecommendation.modelVersion && (
          <p
            style={{
              color: "#64748b",
              fontSize: "12px",
              marginTop: "15px",
            }}
          >
            Model version: {teamRecommendation.modelVersion}
          </p>
        )}
      </>
    ) : (
      <p>No recommendation available in the evaluation response.</p>
    )}

    <div
      style={{
        borderTop: "1px solid #e5e7eb",
        paddingTop: "16px",
        marginTop: "16px",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: "12px",
      }}
    >
      <strong>Workflow Status</strong>

      <span
        style={{
          padding: "7px 12px",
          borderRadius: "8px",
          background: "#f1f5f9",
          color: "#334155",
          fontWeight: 600,
        }}
      >
        {recommendationLabel(evaluation.status)}
      </span>
    </div>

    <p
      style={{
        fontSize: "12px",
        color: "#64748b",
        marginTop: "12px",
        marginBottom: 0,
      }}
    >
      Recommendation only — final approval requires human review.
    </p>
  </div>
)}




            {validationError && (
            <div className="review-message" role="alert">
            Validation failed: {validationError}
            </div>
            )}


{validation && (
  <div
    className="review-message"
    style={{
      background: "#ffffff",
      border: "1px solid #dce2ea",
      borderRadius: "12px",
      padding: "20px",
      marginTop: "16px",
      color: "#1f2937",
    }}
  >
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        flexWrap: "wrap",
        gap: "12px",
        marginBottom: "20px",
      }}
    >
      <h3 style={{ margin: 0 }}>Validation Results</h3>

      <span
        style={{
          padding: "6px 12px",
          borderRadius: "20px",
          background: validation.valid ? "#dcfce7" : "#fee2e2",
          color: validation.valid ? "#166534" : "#991b1b",
          fontWeight: 600,
        }}
      >
        {validation.valid ? "✓ Valid" : "✕ Invalid"}
      </span>
    </div>

    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
        gap: "12px",
        marginBottom: "20px",
      }}
    >
      <div
        style={{
          background: "#f8fafc",
          borderRadius: "10px",
          padding: "16px",
        }}
      >
        <div style={{ color: "#64748b", fontSize: "13px" }}>
          Blocking Issues
        </div>
        <div style={{ fontSize: "28px", fontWeight: 700 }}>
          {blockingIssues.length}
        </div>
      </div>

      <div
        style={{
          background: "#f8fafc",
          borderRadius: "10px",
          padding: "16px",
        }}
      >
        <div style={{ color: "#64748b", fontSize: "13px" }}>
          Review Warnings
        </div>
        <div style={{ fontSize: "28px", fontWeight: 700 }}>
          {reviewFlags.length}
        </div>
      </div>
    </div>

    {blockingIssues.length === 0 ? (
      <p style={{ color: "#166534", marginBottom: "16px" }}>
        ✓ No blocking issues found.
      </p>
    ) : (
      <div style={{ marginBottom: "20px" }}>
        <h4>Blocking Issues</h4>
        {blockingIssues.map((issue, index) => (
          <div
            key={`${issue.code}-${index}`}
            style={{
              background: "#fff1f2",
              borderLeft: "4px solid #dc2626",
              borderRadius: "6px",
              padding: "12px",
              marginBottom: "10px",
            }}
          >
            <strong>
              {issue.field
                ? formatValidationLabel(issue.field)
                : formatValidationLabel(issue.code)}
            </strong>
            <p style={{ margin: "6px 0 0" }}>
              {issue.message}
            </p>
          </div>
        ))}
      </div>
    )}

    {reviewFlags.length > 0 && (
      <div style={{ marginBottom: "20px" }}>
        <h4 style={{ marginBottom: "12px" }}>
          ⚠ Review Required
        </h4>

        {reviewFlags.map((issue, index) => (
          <div
            key={`${issue.code}-${index}`}
            style={{
              background: "#fffbeb",
              borderLeft: "4px solid #f59e0b",
              borderRadius: "6px",
              padding: "12px",
              marginBottom: "10px",
            }}
          >
            <strong>
              {issue.field
                ? formatValidationLabel(issue.field)
                : formatValidationLabel(issue.code)}
            </strong>

            {issue.lineItemId != null && (
              <span style={{ color: "#92400e" }}>
                {" "}— Line Item {issue.lineItemId}
              </span>
            )}

            <p style={{ margin: "6px 0 0", color: "#78350f" }}>
              {issue.message}
            </p>

            <small style={{ color: "#92400e" }}>
              {formatValidationLabel(issue.code)}
            </small>
          </div>
        ))}
      </div>
    )}

    <div
      style={{
        borderTop: "1px solid #e5e7eb",
        paddingTop: "16px",
        display: "flex",
        justifyContent: "space-between",
        gap: "12px",
        alignItems: "center",
      }}
    >
      <strong>Next Status</strong>

      <span
        style={{
          background: "#fef3c7",
          color: "#92400e",
          padding: "7px 12px",
          borderRadius: "8px",
          fontWeight: 600,
        }}
      >
        {formatValidationLabel(validation.nextStatus)}
      </span>
    </div>
  </div>
)}

            

            {hasChanges && (
  <p className="review-recommendation-note">
    Save or discard your changes before validating.
  </p>
            )}

            {saveError && (
              <div className="review-message" role="alert" style={{ color: "#a21d1d" }}>
                {saveError}
              </div>
            )}
            {saveMessage && (
              <div className="review-message review-message-info" role="status">
                {saveMessage}
              </div>
            )}
            <div className="review-message review-message-info">
              {hasChanges
                ? "You have unsaved changes. Save Changes sends PATCH requests to Django."
                : "No unsaved changes."}
            </div>

            <p className="review-recommendation-note"
              style={{ marginTop: "12px" }}
            >
               Human decision actions are integrated with the Team B
              backend. Follow-up and row exclusion features are
              pending further integration.
            </p>
          </div>
        </section>
      </div>
    </main>
  );
} 
