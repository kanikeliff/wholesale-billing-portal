import { apiRequest } from "./apiClient";

export function evaluateBillingRecord(
  recordId: string
): Promise<unknown> {
  return apiRequest<unknown>(
    `/billing-records/${encodeURIComponent(recordId)}/evaluate/`,
    {
      method: "POST",
    }
  );
}
