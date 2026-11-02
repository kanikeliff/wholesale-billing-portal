
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.persistence.models import OCRJob


class OCRJobStatusView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        job = get_object_or_404(
            OCRJob.objects.select_related(
                "document__billing_record"
            ),
            job_id=job_id,
        )

        record = job.document.billing_record

        return Response(
            {
                "jobId": str(job.job_id),
                "recordId": str(record.record_id),
                "documentId": str(job.document_id),
                "ocrStatus": job.status,
                "recordStatus": record.status,
                "attemptCount": job.attempt_count,
                "maxAttempts": job.max_attempts,
                "createdAt": job.created_at,
                "startedAt": job.started_at,
                "completedAt": job.completed_at,
                "nextRetryAt": job.next_retry_at,
                "errorCode": job.error_code,
                "errorMessage": job.error_message,
            },
            status=status.HTTP_200_OK,
        )
