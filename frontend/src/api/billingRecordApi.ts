import { apiRequest } from "./apiClient";

export type FieldQuality =
  | "OK"
  | "LOW_CONFIDENCE"
  | "MISSING"
  | "UNREADABLE"
  | "INVALID";

export interface ExtractedField<T = string | number | null> {
  rawValue: string | null;
  normalizedValue: T;
  confidence: number | null;
  quality: FieldQuality;
}

export interface BillingDocument {
  id: string;
  fileName: string;
  fileUrl: string;
}

export interface LineItem {
  lineItemId: number;
  product: ExtractedField<string | null>;
  grossGallons: ExtractedField<number | null>;
  netGallons: ExtractedField<number | null>;
  e3StockId: ExtractedField<string | null>;
}

export interface Recommendation {
  recommendation: "APPROVE_RECOMMENDED" | "REVIEW_REQUIRED";
  confidence: number;
  rationale: string;
  matchedTerminalLogId: string | null;

  mappedEntities: {
    carrierCode: string | null;
    lineItems: {
      lineItemId: number;
      e3StockId: string | null;
      standardName: string | null;
    }[];
  };

  exceptionIndicators: {
    code: string;
    severity: string;
    message: string;
    field?: string;
    lineItemId?: number;
  }[];
}

export interface BillingRecord {
  recordId: string;
  status: string;

  document: BillingDocument;

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

  recommendation: Recommendation | null;
}

export function getBillingRecord(
  recordId: string
): Promise<BillingRecord> {
  return apiRequest<BillingRecord>(
    `/billing-records/${recordId}/`
  );
}