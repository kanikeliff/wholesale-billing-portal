import { apiRequest } from "./apiClient";

export interface UploadBillingRecordResponse {
  recordId: string;
  status: string;
  documentId: string;
  filename: string;
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
    }
  );
}
