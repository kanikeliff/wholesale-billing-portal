export type FieldQuality =
  | "OK"
  | "LOW_CONFIDENCE"
  | "MISSING"
  | "UNREADABLE"
  | "INVALID";

export type RecordStatus =
  | "UPLOADED"
  | "OCR_PROCESSING"
  | "OCR_COMPLETE"
  | "NEEDS_REVIEW"
  | "RECOMMENDATION_PENDING"
  | "RECOMMENDATION_READY"
  | "APPROVED"
  | "REJECTED"
  | "EXCEPTION";

export interface LineItem {
  lineItemId: number;
  product: string | null;
  e3StockId: string | null;
  netGallons: number | null;
  grossGallons: number | null;

  ocrConfidence?: {
    product?: number;
    netGallons?: number;
    grossGallons?: number;
  };
}

export interface Recommendation {
  recommendation: "APPROVE_RECOMMENDED" | "REVIEW_REQUIRED";
  confidence: number;
  rationale: string;
  matchedTerminalLogId?: string | null;

  exceptionIndicators?: {
    code: string;
    severity: "INFO" | "WARNING" | "HIGH";
    message: string;
    field?: string;
    lineItemId?: number;
  }[];
}

export interface BOLRecord {
  recordId: string;
  bolNumber: string | null;
  contractLifting: string | null;
  origin: string | null;
  supplier: string | null;
  carrier: string | null;
  transactionDate: string | null;
  destination: string | null;

  lineItems: LineItem[];

  ocrConfidence?: {
    bolNumber?: number;
    contractLifting?: number;
    origin?: number;
    supplier?: number;
    carrier?: number;
    transactionDate?: number;
    destination?: number;
  };

  fieldQuality?: Partial<
    Record<
      | "bolNumber"
      | "contractLifting"
      | "origin"
      | "supplier"
      | "carrier"
      | "transactionDate"
      | "destination",
      FieldQuality
    >
  >;

  status: RecordStatus;

  recommendation?: Recommendation;
}