import { useState } from "react";
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

export default function UploadPage() {
  const [selectedFile, setSelectedFile] =
    useState<File | null>(null);

  const [uploadStatus, setUploadStatus] =
    useState<UploadStatus>("idle");

  const [errorMessage, setErrorMessage] =
    useState("");

  const [backendRecord, setBackendRecord] =
    useState<BillingRecord | null>(null);

  const handleFileChange = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    const allowedTypes = [
      "application/pdf",
      "image/jpeg",
      "image/png",
    ];

    if (!allowedTypes.includes(file.type)) {
      setSelectedFile(null);
      setBackendRecord(null);

      setUploadStatus("error");

      setErrorMessage(
        "Unsupported file type. Please upload PDF, JPG, JPEG, or PNG."
      );

      return;
    }

    setSelectedFile(file);
    setBackendRecord(null);

    setUploadStatus("idle");
    setErrorMessage("");
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setUploadStatus("error");

      setErrorMessage(
        "Please select a BOL document first."
      );

      return;
    }

    try {
      setErrorMessage("");
      setBackendRecord(null);

      // Demo upload state
      setUploadStatus("uploading");

      await new Promise((resolve) =>
        setTimeout(resolve, 800)
      );

      // Demo OCR processing state
      setUploadStatus("processing");

      await new Promise((resolve) =>
        setTimeout(resolve, 1000)
      );

      // Real backend GET request
      const record =
        await getBillingRecord("rec_001");

      setBackendRecord(record);

      setUploadStatus("success");
    } catch (error) {
      console.error(error);

      setUploadStatus("error");

      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Unable to retrieve backend OCR data."
      );
    }
  };

  return (
    <div
      style={{
        padding: "32px",
        fontFamily: "Arial, sans-serif",
      }}
    >
      <Link to="/dashboard">
        ← Back to Dashboard
      </Link>

      <h1>Upload BOL</h1>

      <p>
        Upload a Bill of Lading document for OCR
        processing and review.
      </p>

      <hr />

      {/* SELECT DOCUMENT */}

      <div
        style={{
          marginTop: "30px",
          textAlign: "center",
        }}
      >
        <h2>Select Document</h2>

        <input
          type="file"
          accept=".pdf,.jpg,.jpeg,.png"
          onChange={handleFileChange}
        />

        {selectedFile && (
          <p
            style={{
              marginTop: "20px",
            }}
          >
            <strong>Selected File:</strong>{" "}
            {selectedFile.name}
          </p>
        )}

        <button
          type="button"
          onClick={handleUpload}
          disabled={
            !selectedFile ||
            uploadStatus === "uploading" ||
            uploadStatus === "processing"
          }
          style={{
            marginTop: "15px",
            padding: "10px 20px",
            cursor:
              !selectedFile ||
              uploadStatus === "uploading" ||
              uploadStatus === "processing"
                ? "not-allowed"
                : "pointer",
          }}
        >
          Upload
        </button>
      </div>

      {/* UPLOADING */}

      {uploadStatus === "uploading" && (
        <div
          style={{
            marginTop: "35px",
            textAlign: "center",
          }}
        >
          <h2>Uploading Document...</h2>

          <p>
            Preparing the selected BOL for processing.
          </p>
        </div>
      )}

      {/* PROCESSING */}

      {uploadStatus === "processing" && (
        <div
          style={{
            marginTop: "35px",
            textAlign: "center",
          }}
        >
          <h2>Processing OCR...</h2>

          <p>
            Extracting billing information from the BOL.
          </p>
        </div>
      )}

      {/* ERROR */}

      {uploadStatus === "error" && (
        <div
          style={{
            marginTop: "30px",
            textAlign: "center",
          }}
        >
          <p
            style={{
              color: "red",
              fontWeight: "bold",
            }}
          >
            {errorMessage}
          </p>
        </div>
      )}

      {/* SUCCESS */}

      {uploadStatus === "success" &&
        backendRecord && (
          <div
            style={{
              marginTop: "40px",
            }}
          >
            <div
              style={{
                textAlign: "center",
                marginBottom: "30px",
              }}
            >
              <h2>
                OCR Processing Complete
              </h2>

              <p>
                Backend billing record received successfully.
              </p>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns:
                  "1fr 1fr",
                gap: "30px",
                alignItems: "start",
              }}
            >
              {/* ORIGINAL BOL PREVIEW */}

              <div
                style={{
                  border:
                    "1px solid #ccc",
                  borderRadius: "8px",
                  padding: "20px",
                }}
              >
                <h2>
                  Original BOL Preview
                </h2>

                <object
                  data="/sample-bol.pdf"
                  type="application/pdf"
                  width="100%"
                  height="750px"
                  style={{
                    border:
                      "1px solid #ccc",
                    borderRadius: "8px",
                    backgroundColor:
                      "#ffffff",
                  }}
                >
                  <div
                    style={{
                      padding: "20px",
                    }}
                  >
                    <p>
                      PDF preview could not be displayed.
                    </p>

                    <a
                      href="/sample-bol.pdf"
                      target="_blank"
                      rel="noreferrer"
                    >
                      Open PDF
                    </a>
                  </div>
                </object>

                <div
                  style={{
                    marginTop: "12px",
                  }}
                >
                  <a
                    href="/sample-bol.pdf"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Open BOL PDF in New Tab
                  </a>
                </div>
              </div>

              {/* BACKEND OCR RESULT */}

              <div
                style={{
                  border:
                    "1px solid #ccc",
                  borderRadius: "8px",
                  padding: "20px",
                }}
              >
                <h2>
                  Backend OCR Result
                </h2>

                <p>
                  <strong>
                    Record ID:
                  </strong>{" "}
                  {backendRecord.recordId}
                </p>

                <p>
                  <strong>
                    Status:
                  </strong>{" "}
                  {backendRecord.status}
                </p>

                <p>
                  <strong>
                    File:
                  </strong>{" "}
                  {
                    backendRecord
                      .document.fileName
                  }
                </p>

                <h3>
                  JSON Response
                </h3>

                <pre
                  style={{
                    textAlign: "left",
                    backgroundColor:
                      "#111111",
                    color: "#dddddd",
                    padding: "16px",
                    borderRadius: "8px",
                    overflowX: "auto",
                    overflowY: "auto",
                    maxHeight: "650px",
                    fontSize: "13px",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                  }}
                >
                  {JSON.stringify(
                    backendRecord,
                    null,
                    2
                  )}
                </pre>
              </div>
            </div>

            {/* REVIEW DOCUMENT */}

            <div
              style={{
                textAlign: "center",
                marginTop: "30px",
              }}
            >
              <Link
                to={`/records/${backendRecord.recordId}/review`}
              >
                <button
                  style={{
                    padding:
                      "12px 20px",
                    cursor: "pointer",
                  }}
                >
                  Review Document
                </button>
              </Link>
            </div>
          </div>
        )}
    </div>
  );
}