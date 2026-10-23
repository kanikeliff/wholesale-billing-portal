import { apiRequest } from "./apiClient";

export function validateBillingRecord(
  recordId: string
): Promise<unknown> {
  return apiRequest<unknown>(
    `/billing-records/${encodeURIComponent(recordId)}/validate/`,
    {
      method: "POST",
    }
  );
}