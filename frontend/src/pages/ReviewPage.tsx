import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  getBillingRecord,
  type BillingRecord,
  type ExtractedField,
} from "../api/billingRecordApi";

import { mockBols } from "../data/mockBol";

export default function ReviewPage() {
  const { id } = useParams();

  const [record, setRecord] = useState<BillingRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const createMockBillingRecord = (
    mockRecord: (typeof mockBols)[number]
  ): BillingRecord => {
    const makeField = <T,>(
      value: T,
      confidence: number,
      quality: "OK" | "LOW_CONFIDENCE" = "OK"
    ): ExtractedField<T> => ({
      rawValue:
        value === null || value === undefined
          ? null
          : String(value),

      normalizedValue: value,
      confidence,
      quality,
    });

    return {
      recordId: mockRecord.recordId,

      status: mockRecord.status,

      document: {
        id: `doc-${mockRecord.recordId}`,
        fileName: `BOL-${mockRecord.bolNumber}.pdf`,
        fileUrl: "",
      },

      fields: {
        bolNumber: makeField(
          mockRecord.bolNumber,
          0.96
        ),

        contractLifting: makeField(
          "Pending Mapping",
          0.78,
          "LOW_CONFIDENCE"
        ),

        origin: makeField(
          "Terminal Location",
          0.91
        ),

        supplier: makeField(
          mockRecord.supplier,
          0.95
        ),

        carrier: makeField(
          mockRecord.carrier,
          0.89
        ),

        transactionDate: makeField(
          "Oct 9, 2026",
          0.93
        ),

        destination: makeField(
          "Mirabito Facility",
          0.88
        ),
      },

      lineItems: [
        {
          lineItemId: 1,

          product: makeField(
            "Regular Gasoline",
            0.87
          ),

          grossGallons: makeField(
            8550,
            0.92
          ),

          netGallons: makeField(
            8500,
            0.94
          ),

          e3StockId: makeField(
            "Pending",
            0.7,
            "LOW_CONFIDENCE"
          ),
        },
      ],

      recommendation: null,
    };
  };

  useEffect(() => {
    if (!id) {
      setError("Record ID is missing.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError("");

    const loadRecord = async () => {
      try {
        // First try the real Team B backend
        const backendRecord =
          await getBillingRecord(id);

        setRecord(backendRecord);
      } catch (backendError) {
        console.log(
          "Backend record not found. Checking mock records...",
          backendError
        );

        // If backend does not have it,
        // use the dashboard mock record
        const mockRecord = mockBols.find(
          (bol) => bol.recordId === id
        );

        if (mockRecord) {
          setRecord(
            createMockBillingRecord(mockRecord)
          );
        } else {
          setError(
            "Billing record not found."
          );
        }
      } finally {
        setLoading(false);
      }
    };

    loadRecord();
  }, [id]);

  const renderField = (
    label: string,
    field: ExtractedField<string | number | null>
  ) => {
    const needsAttention =
      field.quality === "LOW_CONFIDENCE" ||
      field.quality === "MISSING" ||
      field.quality === "UNREADABLE" ||
      field.quality === "INVALID";

    const displayValue =
      field.normalizedValue === null
        ? "Not available"
        : String(field.normalizedValue);

    const rawValue =
      field.rawValue === null
        ? "Not available"
        : field.rawValue;

    const confidence =
      field.confidence === null
        ? "Unavailable"
        : `${Math.round(
            field.confidence * 100
          )}%`;

    return (
      <div
        style={{
          border: needsAttention
            ? "1px solid orange"
            : "1px solid #444",

          borderRadius: "8px",
          padding: "14px",
          marginBottom: "14px",
        }}
      >
        <p>
          <strong>{label}:</strong>{" "}
          {displayValue}
        </p>

        <p>
          <strong>
            Raw OCR Value:
          </strong>{" "}
          {rawValue}
        </p>

        <p>
          <strong>
            OCR Confidence:
          </strong>{" "}
          {confidence}
        </p>

        <p>
          <strong>
            Quality:
          </strong>{" "}
          {field.quality}
        </p>

        {needsAttention && (
          <p
            style={{
              color: "orange",
              fontWeight: "bold",
            }}
          >
            ⚠ Review recommended
          </p>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <div
        style={{
          padding: "32px",
          fontFamily: "Arial",
        }}
      >
        <h2>
          Loading billing record...
        </h2>
      </div>
    );
  }

  if (error || !record) {
    return (
      <div
        style={{
          padding: "32px",
          fontFamily: "Arial",
        }}
      >
        <Link to="/dashboard">
          ← Back to Dashboard
        </Link>

        <h1>
          Unable to Load Record
        </h1>

        <p>
          {error ||
            "Billing record not found."}
        </p>
      </div>
    );
  }

  return (
    <div
      style={{
        padding: "32px",
        fontFamily:
          "Arial, sans-serif",
      }}
    >
      <Link to="/dashboard">
        ← Back to Dashboard
      </Link>

      <h1>BOL Review</h1>

      <p>
        <strong>
          Record ID:
        </strong>{" "}
        {record.recordId}
      </p>

      <p>
        <strong>
          Status:
        </strong>{" "}
        {record.status}
      </p>

      <p>
        <strong>
          File:
        </strong>{" "}
        {record.document.fileName}
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns:
            "1fr 1fr",
          gap: "30px",
          marginTop: "30px",
          alignItems: "start",
        }}
      >
        {/* ORIGINAL BOL */}

        <div
          style={{
            border:
              "1px solid #ccc",
            borderRadius: "8px",
            padding: "20px",
          }}
        >
          <h2>
            Original BOL
          </h2>

          {record.recordId ===
          "rec_001" ? (
            <>
              <object
                data="/sample-bol.pdf"
                type="application/pdf"
                width="100%"
                height="750px"
                style={{
                  border:
                    "1px solid #ccc",
                  borderRadius:
                    "8px",
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
                    PDF preview could
                    not be displayed.
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

              <p
                style={{
                  marginTop:
                    "12px",
                }}
              >
                <a
                  href="/sample-bol.pdf"
                  target="_blank"
                  rel="noreferrer"
                >
                  Open BOL PDF in New
                  Tab
                </a>
              </p>
            </>
          ) : (
            <img
              src={`/sample-bol-${record.recordId}.png`}
              alt={`Original BOL ${record.recordId}`}
              onError={(
                event
              ) => {
                event.currentTarget.onerror =
                  null;

                event.currentTarget.src =
                  "/sample-bol-rec_001.png";
              }}
              style={{
                width: "100%",
                height: "auto",
                maxHeight:
                  "800px",
                objectFit:
                  "contain",
                borderRadius:
                  "6px",
                backgroundColor:
                  "#ffffff",
                display: "block",
                margin: "0 auto",
              }}
            />
          )}

          <p
            style={{
              color: "#888",
              fontSize: "14px",
              marginTop: "12px",
            }}
          >
            Original BOL document
            preview.
          </p>
        </div>

        {/* EXTRACTED BILLING INFO */}

        <div
          style={{
            border:
              "1px solid #ccc",
            borderRadius: "8px",
            padding: "20px",
          }}
        >
          <h2>
            Extracted Billing
            Information
          </h2>

          {renderField(
            "BOL Number",
            record.fields.bolNumber
          )}

          {renderField(
            "Contract / Lifting",
            record.fields
              .contractLifting
          )}

          {renderField(
            "Origin",
            record.fields.origin
          )}

          {renderField(
            "Supplier",
            record.fields.supplier
          )}

          {renderField(
            "Carrier",
            record.fields.carrier
          )}

          {renderField(
            "Transaction Date",
            record.fields
              .transactionDate
          )}

          {renderField(
            "Destination",
            record.fields
              .destination
          )}
        </div>
      </div>

      {/* PRODUCT LINE ITEMS */}

      <div
        style={{
          border:
            "1px solid #ccc",
          borderRadius: "8px",
          padding: "20px",
          marginTop: "30px",
        }}
      >
        <h2>
          Product Line Items
        </h2>

        {record.lineItems.length ===
          0 && (
          <p>
            No line items were
            found.
          </p>
        )}

        {record.lineItems.map(
          (item) => (
            <div
              key={
                item.lineItemId
              }
              style={{
                border:
                  "1px solid #555",
                borderRadius:
                  "8px",
                padding: "18px",
                marginBottom:
                  "20px",
              }}
            >
              <h3>
                Line Item{" "}
                {item.lineItemId}
              </h3>

              {renderField(
                "Product",
                item.product
              )}

              {renderField(
                "Gross Gallons",
                item.grossGallons
              )}

              {renderField(
                "Net Gallons",
                item.netGallons
              )}

              {renderField(
                "E3 Stock ID",
                item.e3StockId
              )}
            </div>
          )
        )}
      </div>

      {/* TEAM A RECOMMENDATION */}

      <div
        style={{
          border:
            "1px solid #ccc",
          borderRadius: "8px",
          padding: "20px",
          marginTop: "30px",
        }}
      >
        <h2>
          Team A Recommendation
        </h2>

        {record.recommendation ? (
          <>
            <p>
              <strong>
                Recommendation:
              </strong>{" "}
              {
                record
                  .recommendation
                  .recommendation
              }
            </p>

            <p>
              <strong>
                Team A Decision
                Confidence:
              </strong>{" "}
              {Math.round(
                record
                  .recommendation
                  .confidence * 100
              )}
              %
            </p>

            <p>
              <strong>
                Rationale:
              </strong>{" "}
              {
                record
                  .recommendation
                  .rationale
              }
            </p>

            <p>
              <strong>
                Matched Terminal
                Log:
              </strong>{" "}
              {record
                .recommendation
                .matchedTerminalLogId ??
                "Not available"}
            </p>

            {record
              .recommendation
              .mappedEntities && (
              <>
                <h3>
                  Mapped Entities
                </h3>

                <p>
                  <strong>
                    Carrier Code:
                  </strong>{" "}
                  {record
                    .recommendation
                    .mappedEntities
                    .carrierCode ??
                    "Not available"}
                </p>

                {record.recommendation.mappedEntities.lineItems.map(
                  (
                    mappedItem
                  ) => (
                    <div
                      key={
                        mappedItem.lineItemId
                      }
                      style={{
                        border:
                          "1px solid #555",
                        borderRadius:
                          "6px",
                        padding:
                          "12px",
                        marginBottom:
                          "10px",
                      }}
                    >
                      <p>
                        <strong>
                          Line Item:
                        </strong>{" "}
                        {
                          mappedItem.lineItemId
                        }
                      </p>

                      <p>
                        <strong>
                          E3 Stock ID:
                        </strong>{" "}
                        {mappedItem.e3StockId ??
                          "Not available"}
                      </p>

                      <p>
                        <strong>
                          Standard
                          Name:
                        </strong>{" "}
                        {mappedItem.standardName ??
                          "Not available"}
                      </p>
                    </div>
                  )
                )}
              </>
            )}

            {record
              .recommendation
              .exceptionIndicators
              .length > 0 && (
              <>
                <h3>
                  Exception
                  Indicators
                </h3>

                {record.recommendation.exceptionIndicators.map(
                  (
                    exception,
                    index
                  ) => (
                    <div
                      key={`${exception.code}-${index}`}
                      style={{
                        border:
                          "1px solid orange",
                        borderRadius:
                          "6px",
                        padding:
                          "12px",
                        marginBottom:
                          "10px",
                      }}
                    >
                      <p>
                        <strong>
                          Code:
                        </strong>{" "}
                        {
                          exception.code
                        }
                      </p>

                      <p>
                        <strong>
                          Severity:
                        </strong>{" "}
                        {
                          exception.severity
                        }
                      </p>

                      <p>
                        <strong>
                          Message:
                        </strong>{" "}
                        {
                          exception.message
                        }
                      </p>

                      {exception.field && (
                        <p>
                          <strong>
                            Field:
                          </strong>{" "}
                          {
                            exception.field
                          }
                        </p>
                      )}

                      {exception.lineItemId !==
                        undefined && (
                        <p>
                          <strong>
                            Line Item:
                          </strong>{" "}
                          {
                            exception.lineItemId
                          }
                        </p>
                      )}
                    </div>
                  )
                )}
              </>
            )}
          </>
        ) : (
          <>
            <p>
              Recommendation has
              not been generated
              yet.
            </p>

            <p
              style={{
                color: "#888",
              }}
            >
              Team A recommendation
              will appear here after
              evaluation.
            </p>
          </>
        )}
      </div>

      {/* ACTIONS */}

      <div
        style={{
          display: "flex",
          gap: "12px",
          marginTop: "30px",
        }}
      >
        <button>
          Approve
        </button>

        <button>
          Reject
        </button>

        <button>
          Mark Exception
        </button>
      </div>
    </div>
  );
}