import { apiRequest } from "./apiClient";
import type { Recommendation } from "./billingRecordApi";

export interface EvaluationResponse {
  recordId: string;
  status: string;
  pending: boolean;
  recommendation?: Recommendation | null;
  error?: { code: string; message: string; retryable?: boolean };
}

export function evaluateBillingRecord(
  recordId: string
): Promise<EvaluationResponse> {
  return apiRequest<EvaluationResponse>(
    `/billing-records/${encodeURIComponent(recordId)}/evaluate/`,
    {
      method: "POST",
      // The existing backend can make four 30s attempts plus 14s backoff.
      timeoutMs: 150000,
    }
  );
}
