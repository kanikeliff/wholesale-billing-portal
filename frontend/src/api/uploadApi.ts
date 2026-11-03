import { apiRequest } from "./apiClient";

export interface UploadBillingRecordResponse {
  recordId: string;
  documentId: string;
  jobId: string;
  status: string;
  ocrStatus: string;
  documentUrl: string;
}

export function uploadBillingRecord(
  file: File
): Promise<UploadBillingRecordResponse> {
  const formData = new FormData();
  formData.append("file", file);

  return apiRequest<UploadBillingRecordResponse>(
    "/billing-records/upload/",
    {
      method: "POST",
      body: formData,
      timeoutMs: 60000,
    }
  );
}
