
import { apiRequest } from "./apiClient";

export type FieldQuality =
  | "OK"
  | "LOW_CONFIDENCE"
  | "MISSING"
  | "UNREADABLE"
  | "INVALID";

export interface ExtractedField<T = string | number | null> {
  normalizedValue: T;
  rawValue?: string | null;
  confidence?: number | null;
  // Quality and confidence describe the original OCR evidence.
  quality?: FieldQuality;
  // Derived from persisted human correction audit events.
  isCorrected?: boolean;
}

export interface BillingDocument {
  documentId?: string;
  recordId?: string;
  originalFilename?: string | null;
  mimeType?: string;
  fileSizeBytes?: number;
  checksumSha256?: string;
  storagePath?: string;
  documentUrl?: string | null;
  createdAt?: string;
  id?: string;
  fileName?: string;
  fileUrl?: string;
}

export interface LineItem {
  lineItemId: string;
  lineNumber?: number;

  product: ExtractedField<string | null>;
  grossGallons: ExtractedField<number | null>;
  netGallons: ExtractedField<number | null>;
  e3StockId: ExtractedField<string | null>;
  standardName?: ExtractedField<string | null>;
}

export interface Recommendation {
  recommendation:
    | "APPROVE_RECOMMENDED"
    | "REVIEW_REQUIRED"
    | "REJECT_RECOMMENDED";
  confidence: number | null;
  modelVersion?: string | null;
  revision?: number;
  rationale: string;
  matchedTerminalLogId: string | null;

  mappedEntities: {
    carrierCode: string | null;
    lineItems: {
      lineItemId: string;
      e3StockId: string | null;
      standardName: string | null;
    }[];
  };

  exceptionIndicators: {
    code: string;
    severity: string;
    message: string;
    field?: string;
    lineItemId?: string;
  }[];
}

export interface BillingRecord {
  ocrJob?: {
    jobId: string;
    status: string;
    errorCode: string | null;
    errorMessage: string | null;
  } | null;
  recordId: string;
  status: string;

  // Record detail may include the persisted source document and recommendation.
  document?: BillingDocument | null;
  recommendation?: Recommendation | null;

  fields: {
    bolNumber: ExtractedField<string | null>;
    contractLifting: ExtractedField<string | null>;
    origin: ExtractedField<string | null>;
    supplier: ExtractedField<string | null>;
    carrier: ExtractedField<string | null>;
    transactionDate: ExtractedField<string | null>;
    destination: ExtractedField<string | null>;
  };

  lineItems: LineItem[];

  createdAt?: string;
  updatedAt?: string;
}

export interface BillingRecordListResponse {
  count: number;
  records: BillingRecord[];
}

export type BillingRecordSummary = BillingRecord;

export function getBillingRecord(
  recordId: string
): Promise<BillingRecord> {
  return apiRequest<BillingRecord>(
    `/billing-records/${encodeURIComponent(recordId)}/`
  );
}

export function getBillingRecords():
  Promise<BillingRecordListResponse> {
  return apiRequest<BillingRecordListResponse>(
    "/billing-records/"
  );
}
