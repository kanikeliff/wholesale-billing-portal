import BolPdfViewer from "../components/BolPdfViewer";
import { useEffect, useState, type ChangeEvent } from "react";
import { Link } from "react-router-dom";

import {
  getBillingRecord,
  type BillingRecord,
} from "../api/billingRecordApi";

type UploadStatus =
  | "idle"
  | "uploading"
  | "processing"
  | "success"
  | "error";

const colors = {
  brand: "#b21f36",
  brandHover: "#95192d",
  background: "#f4f6f9",
  white: "#ffffff",
  text: "#202938",
  muted: "#667085",
  border: "#e2e6ed",
};

export default function UploadPage() {
  
  const [selectedFile, setSelectedFile] =
    useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");

  // Local preview of the actual selected file; not a server document URL.
  useEffect(() => {
    if (!selectedFile) {
      setPreviewUrl("");
      return;
    }
    const url = URL.createObjectURL(selectedFile);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [selectedFile]);

  const [uploadStatus, setUploadStatus] =
    useState<UploadStatus>("idle");

  const [errorMessage, setErrorMessage] = useState("");
  const [backendRecord, setBackendRecord] =
    useState<BillingRecord | null>(null);

  const isProcessing =
    uploadStatus === "uploading" ||
    uploadStatus === "processing";

  // File validation: PDF, JPG, JPEG and PNG.
  const handleFileChange = (
    event: ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0];

    setSelectedFile(null);
    setBackendRecord(null);
    setUploadStatus("idle");
    setErrorMessage("");

    if (!file) return;

    const allowedTypes = [
      "application/pdf",
      "image/jpeg",
      "image/png",
    ];

    const validExtension =
      /\.(pdf|jpe?g|png)$/i.test(file.name);

    if (
      !allowedTypes.includes(file.type) ||
      !validExtension
    ) {
      setUploadStatus("error");
      setErrorMessage(
        "Unsupported file type. Please select a PDF, JPG, JPEG, or PNG file."
      );
      event.target.value = "";
      return;
    }

    if (file.size === 0) {
      setUploadStatus("error");
      setErrorMessage("The selected file is empty.");
      event.target.value = "";
      return;
    }

    setSelectedFile(file);
  };

  
  // Upload the selected document. Never substitute a seeded/mock billing record.
  const handleUpload = async () => {
    if (!selectedFile || isProcessing) return;

    setErrorMessage("");
    setBackendRecord(null);
    setUploadStatus("uploading");

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const baseUrl = (
        import.meta.env.VITE_API_BASE_URL ||
        "http://127.0.0.1:8000/api/v1"
      ).replace(/\/$/, "");

      // Do not set Content-Type manually; the browser supplies the boundary.
      const response = await fetch(`${baseUrl}/billing-records/upload/`, {
        method: "POST",
        body: formData,
      });
      const result: unknown = await response.json().catch(() => null);
      const payload =
        result && typeof result === "object"
          ? (result as Record<string, unknown>)
          : {};
      const backendMessage =
        typeof payload.message === "string"
          ? payload.message
          : typeof payload.detail === "string"
          ? payload.detail
          : null;

      if (response.status === 503) {
        throw new Error(
          backendMessage ||
            "The backend upload endpoint is reachable, but OCR processing is not configured yet (HTTP 503)."
        );
      }
      if (response.status === 202) {
        throw new Error(
          "Upload accepted for asynchronous processing (HTTP 202). The backend must provide a job-status endpoint before the result can be opened."
        );
      }
      if (!response.ok) {
        throw new Error(
          backendMessage || `Upload failed (HTTP ${response.status}).`
        );
      }

      const recordId = payload.recordId;
      if (typeof recordId !== "string" || !recordId.trim()) {
        throw new Error(
          "The upload response did not include a saved billing record ID."
        );
      }

      setUploadStatus("processing");
      // Confirm the uploaded record is readable through the existing API.
      const savedRecord = await getBillingRecord(recordId);
      setBackendRecord(savedRecord);
      setUploadStatus("success");
    } catch (error) {
      console.error("BOL upload failed:", error);
      setUploadStatus("error");
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Unable to upload the BOL document."
      );
    }
  };

  const fileSize = selectedFile
    ? `${(selectedFile.size / 1024).toFixed(1)} KB`
    : "";

    const statusLabel =
    uploadStatus === "uploading"
      ? "Uploading BOL"
      : uploadStatus === "processing"
      ? "Loading Saved Record"
      : uploadStatus === "success"
      ? "BOL Uploaded Successfully"
      : uploadStatus === "error"
      ? "Action Required"
      : "Select Document";

  return (
    <main className="upload-page">
      <style>{`
        .upload-page {
          min-height: 100vh;
          background: ${colors.background};
          color: ${colors.text};
          padding: 28px;
          font-family: Inter, system-ui, sans-serif;
          text-align: left;
        }

        .upload-page * {
          box-sizing: border-box;
        }

        .upload-container {
          width: 100%;
          max-width: 1480px;
          margin: 0 auto;
        }

        .upload-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 16px;
          background: white;
          padding: 24px 28px;
          border: 1px solid #e2e6ed;
          border-radius: 12px;
          margin-bottom: 22px;
        }

        .upload-header h1 {
          font-size: 28px;
          font-weight: 750;
          margin: 0 0 6px;
          color: #202938;
        }

        .upload-subtitle {
          color: #667085;
          font-size: 14px;
          margin: 0;
        }

        .upload-back {
          color: #b21f36;
          text-decoration: none;
          font-size: 14px;
          font-weight: 650;
        }

        .upload-card {
          background: white;
          border: 1px solid #e2e6ed;
          border-radius: 12px;
          padding: 24px;
          margin-bottom: 22px;
          min-width: 0;
        }

        .upload-card h2 {
          color: #202938;
          font-size: 19px;
          font-weight: 700;
          margin: 0 0 8px;
        }

        .upload-card h3 {
          color: #202938;
          font-size: 16px;
          margin: 18px 0 10px;
        }

        .upload-description {
          color: #667085;
          font-size: 13px;
          line-height: 1.6;
          margin: 0 0 20px;
        }

        .upload-dropzone {
          border: 2px dashed #cdd5df;
          border-radius: 10px;
          background: #fafbfc;
          padding: 28px 20px;
          text-align: center;
        }

        .upload-dropzone label {
          display: block;
          font-weight: 650;
          color: #344054;
          margin-bottom: 14px;
        }

        .upload-file-input {
          max-width: 100%;
          font-size: 13px;
          color: #344054;
        }

        .upload-file-input::file-selector-button {
          background: #ffffff;
          border: 1px solid #cdd5df;
          border-radius: 6px;
          padding: 10px 14px;
          margin-right: 14px;
          cursor: pointer;
          color: #344054;
          font-weight: 600;
        }

        .upload-selected-file {
          margin-top: 18px;
          padding: 14px 16px;
          background: #f6f8fb;
          border: 1px solid #e2e6ed;
          border-radius: 8px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 10px;
          font-size: 13px;
        }

        .upload-button {
          border: 1px solid #b21f36;
          background: #b21f36;
          color: white;
          border-radius: 7px;
          padding: 12px 22px;
          font-size: 14px;
          font-weight: 700;
          min-height: 44px;
          cursor: pointer;
        }

        .upload-button:hover:not(:disabled) {
          background: #95192d;
        }

        .upload-button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .upload-button-secondary {
          border: 1px solid #cdd5df;
          background: white;
          color: #344054;
          border-radius: 7px;
          padding: 12px 18px;
          font-weight: 600;
          font-size: 13px;
          text-decoration: none;
          display: inline-block;
        }

        .upload-actions {
          display: flex;
          gap: 12px;
          flex-wrap: wrap;
          margin-top: 20px;
          align-items: center;
        }

        .upload-demo-notice {
          background: #fff8e8;
          border: 1px solid #f0d79f;
          color: #805200;
          padding: 12px 16px;
          border-radius: 8px;
          font-size: 13px;
          line-height: 1.6;
          margin-bottom: 20px;
        }

        .upload-status {
          background: #f5f7fa;
          border: 1px solid #e2e6ed;
          border-radius: 8px;
          padding: 18px;
          margin-bottom: 20px;
        }

        .upload-status strong {
          color: #202938;
        }

        .upload-status p {
          font-size: 13px;
          color: #667085;
          margin: 6px 0 0;
        }

        .upload-status-pill {
          display: inline-flex;
          background: #fcecef;
          color: #b21f36;
          border-radius: 20px;
          padding: 6px 12px;
          font-size: 12px;
          font-weight: 700;
          margin-bottom: 12px;
        }

        .upload-error {
          background: #fef2f2;
          color: #b91c1c;
          border: 1px solid #fecaca;
          border-radius: 8px;
          padding: 14px 16px;
          margin-top: 16px;
          font-size: 13px;
        }

        .upload-result-grid {
          display: grid;
          grid-template-columns:
            minmax(0, 1fr) minmax(0, 1fr);
          gap: 20px;
          align-items: start;
        }

        .upload-preview-card {
          background: white;
          border: 1px solid #e2e6ed;
          border-radius: 10px;
          padding: 20px;
          min-width: 0;
        }

        .upload-preview-card h2 {
          font-size: 18px;
          color: #202938;
          margin: 0 0 8px;
        }

        .upload-pdf {
          display: block;
          width: 100%;
          height: 650px;
          border: 1px solid #e2e6ed;
          border-radius: 7px;
          background: white;
        }

        .upload-pdf-actions {
          margin-top: 12px;
          text-align: right;
        }

        .upload-pdf-actions a {
          color: #b21f36;
          font-size: 13px;
          font-weight: 650;
        }

        .upload-record-info {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
          margin: 18px 0;
        }

        .upload-info-box {
          background: #f8f9fb;
          border: 1px solid #e2e6ed;
          border-radius: 7px;
          padding: 12px;
          min-width: 0;
        }

        .upload-info-label {
          display: block;
          color: #667085;
          font-size: 11px;
          margin-bottom: 7px;
        }

        .upload-info-value {
          display: block;
          color: #202938;
          font-size: 13px;
          font-weight: 650;
          overflow-wrap: anywhere;
        }

        .upload-json {
          background: #f8f9fb;
          color: #344054;
          border: 1px solid #e2e6ed;
          border-radius: 8px;
          padding: 16px;
          max-height: 470px;
          overflow: auto;
          font-size: 12px;
          line-height: 1.7;
          text-align: left;
          white-space: pre-wrap;
          overflow-wrap: anywhere;
        }

        .upload-json-details summary {
          cursor: pointer;
          font-size: 13px;
          color: #b21f36;
          font-weight: 650;
          padding: 12px 0;
        }

        .upload-success-banner {
          background: #ecfdf3;
          border: 1px solid #a6f4c5;
          color: #067647;
          border-radius: 8px;
          padding: 14px 16px;
          font-size: 13px;
          margin-bottom: 20px;
        }

        .upload-review-footer {
          display: flex;
          justify-content: flex-end;
          align-items: center;
          gap: 16px;
          flex-wrap: wrap;
          margin-top: 22px;
        }

        .upload-review-footer a.upload-button {
          text-decoration: none;
        }

        .upload-review-footer a.upload-button:hover {
          color: white;
          text-decoration: none;
        }

        @media (max-width: 850px) {
          .upload-page {
            padding: 14px;
          }

          .upload-header {
            padding: 20px;
          }

          .upload-result-grid {
            grid-template-columns: minmax(0, 1fr);
          }

          .upload-record-info {
            grid-template-columns: minmax(0, 1fr);
          }

          .upload-pdf {
            height: 480px;
          }
        }
      `}</style>

      <div className="upload-container">
        {/* HEADER */}
        <header className="upload-header">
          <div>
            <h1>Upload BOL</h1>
            <p className="upload-subtitle">
              Wholesale Billing Portal · Document Intake
            </p>
          </div>

          <Link to="/dashboard" className="upload-back">
            ← Back to Dashboard
          </Link>
        </header>

        {/* DOCUMENT SELECTION */}
        <section className="upload-card">
          <h2>Select Document</h2>
          <p className="upload-description">
            Select a Bill of Lading document to upload
            and process using the backend OCR pipeline.
            Supported formats: PDF, JPG, JPEG and PNG.
          </p>

          <div className="upload-dropzone">
            <label htmlFor="bol-file">
              Choose a BOL document
            </label>

            <input
              id="bol-file"
              type="file"
              accept=".pdf,.jpg,.jpeg,.png"
              onChange={handleFileChange}
              disabled={isProcessing}
              className="upload-file-input"
            />
          </div>

          {selectedFile && (
            <div className="upload-selected-file">
              <div>
                <strong>{selectedFile.name}</strong>
                <div style={{
                  color: colors.muted,
                  marginTop: 5
                }}>
                  {fileSize} · Local selection
                </div>
              </div>
              <span style={{
                color: "#067647",
                fontWeight: 650
              }}>
                Valid file type
              </span>
            </div>
          )}

          <div className="upload-actions">
            <button
              type="button"
              className="upload-button"
              onClick={handleUpload}
              disabled={!selectedFile || isProcessing}
            >
              {isProcessing
                ? "Uploading / processing..."
                : "Upload & Process BOL"}
            </button>

            <span style={{
              color: colors.muted,
              fontSize: 12
            }}>
              Your selected file will be sent to the Django backend.
            </span>
          </div>

          {uploadStatus !== "idle" &&
            uploadStatus !== "error" && (
              <div className="upload-status"
                style={{ marginTop: 20 }}
                role="status"
              >
                <span className="upload-status-pill">
                  {statusLabel}
                </span>
                <strong>
                  {uploadStatus === "success"
                    ? "Billing record saved successfully"
                    : "Processing document"}
                </strong>

                <p>
                  {uploadStatus === "uploading"
                    ? "Sending the selected BOL document to the backend..."
                    : uploadStatus === "processing"
                    ? "Retrieving the saved billing record..."
                    : "The billing record is ready for review."}
                </p>
              </div>
            )}

          {uploadStatus === "error" && (
            <div className="upload-error" role="alert">
              <strong>Unable to continue.</strong>
              <div style={{ marginTop: 6 }}>
                {errorMessage}
              </div>
            </div>
          )}
        </section>

        {/* BACKEND RESULT */}
        {uploadStatus === "success" &&
          backendRecord && (
            <section className="upload-card">
              <div className="upload-success-banner">
                BOL processed and saved by the backend successfully.
              </div>

              <h2>OCR Result</h2>
              <p className="upload-description">
                Compare the selected document with
                its extracted billing information.
                Continue to the Review Workspace
                to inspect individual fields.
              </p>

              <div className="upload-result-grid">
                {/* ORIGINAL BOL */}
                <div className="upload-preview-card">
                  <h2>Original BOL Preview</h2>
                  <p className="upload-description">
                    {selectedFile?.name ?? "Original BOL"}
                    {" · "}Local preview
                  </p>

                  {previewUrl ? (
                    selectedFile?.type === "application/pdf" ? (
                      <BolPdfViewer fileUrl={previewUrl} />
                    ) : (
                      <img
                        src={previewUrl}
                        alt="Selected BOL document"
                        style={{ width: "100%", height: "auto", objectFit: "contain" }}
                      />
                    )
                  ) : (
                    <p>No local document preview available.</p>
                  )}

                  {previewUrl && (
                    <div className="upload-pdf-actions">
                      <a href={previewUrl} target="_blank" rel="noreferrer">
                        Open Selected Document ↗
                      </a>
                    </div>
                  )}
                </div>

                {/* OCR RESULT */}
                <div className="upload-preview-card">
                  <h2>Backend OCR Result</h2>
                  <p className="upload-description">
                    Structured billing data retrieved
                    from the existing backend API.
                  </p>

                  <div className="upload-record-info">
                    <div className="upload-info-box">
                      <span className="upload-info-label">
                        Record ID
                      </span>
                      <span className="upload-info-value">
                        {backendRecord.recordId}
                      </span>
                    </div>

                    <div className="upload-info-box">
                      <span className="upload-info-label">
                        Workflow Status
                      </span>
                      <span className="upload-info-value">
                        {backendRecord.status.replace(
                          /_/g,
                          " "
                        )}
                      </span>
                    </div>

                    <div className="upload-info-box">
                      <span className="upload-info-label">
                        BOL Number
                      </span>
                      <span className="upload-info-value">
                        {backendRecord.fields.bolNumber
                          .normalizedValue ?? "Not available"}
                      </span>
                    </div>

                    <div className="upload-info-box">
                      <span className="upload-info-label">
                        Supplier
                      </span>
                      <span className="upload-info-value">
                        {backendRecord.fields.supplier
                          .normalizedValue ?? "Not available"}
                      </span>
                    </div>

                    <div className="upload-info-box">
                      <span className="upload-info-label">
                        Product Line Items
                      </span>
                      <span className="upload-info-value">
                        {backendRecord.lineItems.length}
                      </span>
                    </div>

                    <div className="upload-info-box">
                      <span className="upload-info-label">
                        Source File
                      </span>
                      <span className="upload-info-value">
                      {selectedFile?.name ?? "Unavailable"}
                      </span>
                    </div>
                  </div>

                  <details className="upload-json-details">
                    <summary>
                      View Raw Backend JSON
                    </summary>

                    <pre className="upload-json">
                      {JSON.stringify(
                        backendRecord,
                        null,
                        2
                      )}
                    </pre>
                  </details>
                </div>
              </div>

              {/* REVIEW DOCUMENT */}
              <div className="upload-review-footer">
                <span style={{
                  fontSize: 13,
                  color: colors.muted
                }}>
                  Ready to inspect the saved OCR fields.
                </span>

                <Link
                  to={`/records/${encodeURIComponent(
                    backendRecord.recordId
                  )}/review`}
                  className="upload-button"
                >
                  Review Document →
                </Link>
              </div>
            </section>
          )}
      </div>
    </main>
  );
}
