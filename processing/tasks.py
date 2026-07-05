import pandas as pd
from celery import shared_task
from django.core.cache import cache
from uploads.models import Upload
from jobs.models import Job
from processing.spark import run_replacement
from processing.llm import generate_regex

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=5,
    name="processing.tasks.inspect_upload",
)
def inspect_upload_task(self, upload_id: str):
    """
    Inspect an uploaded file and populate Upload.column_meta and Upload.row_count.
    """

    try:
        upload = Upload.objects.get(pk=upload_id)
        upload.status = Upload.Status.PENDING
        upload.save(update_fields=["status", "updated_at"])

        # Read the file and extract metadata
        column_meta, row_count = _inspect_file(upload.file_path, upload.mime_type)

        upload.column_meta = column_meta
        upload.row_count = row_count
        upload.status = Upload.Status.READY
        upload.save(update_fields=["column_meta", "row_count", "status", "updated_at"])
    except Exception as exc:
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 5)


def _inspect_file(file_path: str, mime_type: str) -> tuple[list, int]:
    """
    Read the file to get column names and row count.
    """

    if mime_type in ("application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"):
        df = pd.read_excel(file_path, nrows=0)   # nrows=0 gets headers only
        full_df = pd.read_excel(file_path)
        row_count = len(full_df)
    elif mime_type in ("application/csv", "text/csv"):
        df = pd.read_csv(file_path, nrows=0)
        with open(file_path, "r") as f:
            row_count = sum(1 for _ in f) - 1

    column_meta = [
        {"name": col, "dtype": str(df.dtypes.get(col, "object"))}
        for col in df.columns
    ]

    return column_meta, row_count


@shared_task(
    bind=True,
    max_retries=1,
    name="processing.tasks.run_job",
    soft_time_limit=1800,
    time_limit=2100,
)
def run_job_task(self, job_id: str):

    try:
        job = Job.objects.get(pk=job_id)
    except Job.DoesNotExist:
        return

    try:
        # Mark running
        job.mark_running(celery_task_id=self.request.id)
        job.update_progress(5)

        # Generate regex
        regex_pattern = generate_regex(job.nl_prompt)
        job.regex_pattern = regex_pattern
        job.save(update_fields=["regex_pattern", "updated_at"])
        job.update_progress(20)

        # Spark replacement
        def progress_callback(pct: int):
            mapped = 20 + int(pct * 0.7)
            job.update_progress(mapped)

        result_path = run_replacement(
            file_path = job.upload.file_path,
            mime_type = job.upload.mime_type,
            target_columns = job.target_columns,
            regex_pattern = regex_pattern,
            replacement = job.replacement,
            job_id = str(job.id),
            progress_callback = progress_callback,
        )

        # Mark success
        job.mark_success(
            result_path = result_path,
            regex_pattern = regex_pattern,
        )

    except Exception as exc:
        job.mark_failed(error=str(exc))
        raise