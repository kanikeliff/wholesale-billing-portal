import { apiRequest } from "./apiClient";

export interface CorrectionResponse {
  oldValue?: unknown;
  newValue?: unknown;
  status?: string;
  requiresReevaluation?: boolean;
}

export function updateBillingField(
  recordId: string,
  fieldName: string,
  value: string | number | null,
  reviewedBy: string
): Promise<CorrectionResponse> {
  return apiRequest<CorrectionResponse>(
    `/billing-records/${encodeURIComponent(recordId)}/fields/${encodeURIComponent(fieldName)}/`,
    {
      method: "PATCH",
      body: JSON.stringify({ value, reviewedBy }),
    }
  );
}

export function updateBillingLineItem(
  recordId: string,
  lineItemId: string | number,
  fieldName: string,
  value: string | number | null,
  reviewedBy: string
): Promise<CorrectionResponse> {
  return apiRequest<CorrectionResponse>(
    `/billing-records/${encodeURIComponent(recordId)}/line-items/${encodeURIComponent(String(lineItemId))}/${encodeURIComponent(fieldName)}/`,
    {
      method: "PATCH",
      body: JSON.stringify({ value, reviewedBy }),
    }
  );
}
