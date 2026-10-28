
import { apiRequest } from "./apiClient";

export type HumanDecision =
  | "APPROVE"
  | "REJECT"
  | "EXCEPTION";

export interface DecisionResponse {
  recordId: string;
  decision: HumanDecision;
  previousStatus: string;
  status: string;
  decidedBy: string | null;
  reason: string | null;
}

export function submitBillingDecision(
  recordId: string,
  decision: HumanDecision,
  reason: string
): Promise<DecisionResponse> {
  return apiRequest<DecisionResponse>(
    `/billing-records/${encodeURIComponent(recordId)}/decision/`,
    {
      method: "POST",
      body: JSON.stringify({
        decision,
        reason,
      }),
    }
  );
}

