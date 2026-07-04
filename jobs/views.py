import os
import math
import pandas as pd
from .models import Job
from rest_framework import status
from uploads.models import Upload
from celery.result import AsyncResult
from rest_framework.views import APIView
from processing.tasks import run_job_task
from rest_framework.response import Response
from .serializers import JobSerializer, JobCreateSerializer
from rest_framework.exceptions import NotFound, ValidationError
from backend.core_utils import get_client_id


class JobListCreateView(APIView):

    def get(self, request):
        client_id = get_client_id(request)
        jobs = Job.objects.filter(
            session_key=client_id
        ).select_related('upload').order_by('-created_at')
        return Response(JobSerializer(jobs, many=True).data)

    def post(self, request):
        """
        Create a job and dispatch it to Celery immediately.
        Returns the job_id.
        """
        client_id = get_client_id(request)

        serializer = JobCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Verify the upload belongs to this client
        try:
            upload = Upload.objects.get(
                pk=data["upload_id"],
                session_key=client_id,
            )
        except Upload.DoesNotExist:
            raise NotFound("Upload not found.")

        # check if upload is in ready state
        if upload.status != Upload.Status.READY:
            raise ValidationError(
                f"Upload is not ready yet (status: {upload.status}). "
                "Wait for inspection to complete."
            )

        # Validate requested columns exist in the upload
        available_columns = [col["name"] for col in upload.column_meta]
        invalid_columns = [
            col for col in data["target_columns"]
            if col not in available_columns
        ]
        if invalid_columns:
            raise ValidationError(
                f"Columns not found in upload: {invalid_columns}. "
                f"Available: {available_columns}"
            )

        # Create job record
        job = Job.objects.create(
            session_key = client_id,
            upload = upload,
            nl_prompt = data["nl_prompt"],
            target_columns = data["target_columns"],
            replacement = data["replacement"],
            status = Job.Status.QUEUED,
        )

        # Dispatch to Celery
        run_job_task.delay(str(job.id))

        return Response(JobSerializer(job).data, status=status.HTTP_201_CREATED)

    def delete(self, request):
        client_id = get_client_id(request)

        jobs = Job.objects.filter(session_key=client_id)

        # Revoke any running tasks
        for job in jobs.filter(status__in=["QUEUED", "RUNNING"]):
            if job.celery_task_id:
                AsyncResult(job.celery_task_id).revoke(terminate=True)

        # Clean up result files
        import shutil
        for job in jobs:
            if job.result_path and os.path.exists(job.result_path):
                shutil.rmtree(job.result_path, ignore_errors=True)

        jobs.delete()
        return Response({"detail": "All jobs deleted."}, status=status.HTTP_200_OK)


class JobDetailView(APIView):

    def get(self, request, pk):
        """get job status and progress."""
        job = self._get_owned_job(request, pk)
        return Response(JobSerializer(job).data)

    def delete(self, request, pk):
        """Cancel a running job."""
        job = self._get_owned_job(request, pk)

        if job.status not in (Job.Status.QUEUED, Job.Status.RUNNING):
            raise ValidationError("Only QUEUED or RUNNING jobs can be cancelled.")

        # Revoke the Celery task
        if job.celery_task_id:
            AsyncResult(job.celery_task_id).revoke(terminate=True)

        job.status = Job.Status.CANCELLED
        job.save(update_fields=["status", "updated_at"])

        return Response({"detail": "Job cancelled."}, status=status.HTTP_200_OK)

    def _get_owned_job(self, request, pk):
        client_id = get_client_id(request)
        try:
            return Job.objects.get(
                pk=pk,
                session_key=client_id,
            )
        except Job.DoesNotExist:
            raise NotFound("Job not found.")


class JobResultView(APIView):

    def get(self, request, pk):
        """
        Return paginated result rows from the Parquet file.
        """
        job = self._get_owned_job(request, pk)

        if job.status != Job.Status.SUCCESS:
            raise ValidationError(
                f"Job is not complete yet (status: {job.status})."
            )

        # Pagination
        try:
            page = max(1, int(request.query_params.get("page", 1)))
            page_size = min(100, max(1, int(request.query_params.get("page_size", 50))))
        except ValueError:
            raise ValidationError("page and page_size must be integers.")

        rows, total_rows, total_pages = _read_parquet_page(
            job.result_path, page, page_size
        )

        return Response({
            "job_id": str(job.id),
            "page": page,
            "page_size": page_size,
            "total_rows": total_rows,
            "total_pages": total_pages,
            "regex_used": job.regex_pattern,
            "columns": job.upload.column_meta,
            "rows": rows,
        })

    def _get_owned_job(self, request, pk):
        client_id = get_client_id(request)
        try:
            return Job.objects.get(
                pk=pk,
                session_key=client_id,
            )
        except Job.DoesNotExist:
            raise NotFound("Job not found.")


def _read_parquet_page(result_path: str, page: int, page_size: int):
    """
    Read a page of rows from the Parquet result.
    """

    parquet_file = None
    for fname in os.listdir(result_path):
        if fname.endswith(".parquet"):
            parquet_file = os.path.join(result_path, fname)
            break

    if not parquet_file:
        raise ValidationError("Result file not found.")

    df = pd.read_parquet(parquet_file)
    total_rows = len(df)
    total_pages = max(1, math.ceil(total_rows / page_size))

    start = (page - 1) * page_size
    end = start + page_size
    page_df = df.iloc[start:end]

    # Convert to list of dicts for JSON
    rows = page_df.fillna("").astype(str).to_dict(orient="records")

    return rows, total_rows, total_pages