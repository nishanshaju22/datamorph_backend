import uuid
from django.db import models
from uploads.models import Upload


class Job(models.Model):
    """
    Represents a single pattern-replace operation against an Upload.

    Tracks the full lifecycle: queued → running → success/failed.
    Progress is an integer 0-100 updated by the Celery task.
    """

    class Status(models.TextChoices):
        QUEUED = "QUEUED", "Queued"
        RUNNING = "RUNNING", "Running"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_key = models.CharField(max_length=40, db_index=True)
    upload = models.ForeignKey(Upload, on_delete=models.CASCADE, related_name="jobs")

    # --- user inputs ---
    nl_prompt = models.TextField()
    target_columns = models.JSONField(default=list)
    replacement = models.CharField(max_length=1024)

    # --- derived / outputs ---
    regex_pattern = models.CharField(max_length=2048, blank=True)  # LLM output
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    progress = models.PositiveSmallIntegerField(default=0) # 0-100
    error_message = models.TextField(blank=True)
    result_path = models.CharField(max_length=1024, blank=True)   # Parquet output path
    celery_task_id = models.CharField(max_length=255, blank=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes  = [
            models.Index(fields=["session_key", "created_at"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"Job({self.status}, {self.progress}%, upload={self.upload_id})"

    def mark_running(self, celery_task_id: str) -> None:
        """Transition to RUNNING atomically."""
        self.status = self.Status.RUNNING
        self.celery_task_id = celery_task_id
        self.save(update_fields=["status", "celery_task_id", "updated_at"])

    def mark_success(self, result_path: str, regex_pattern: str) -> None:
        self.status = self.Status.SUCCESS
        self.progress = 100
        self.result_path = result_path
        self.regex_pattern = regex_pattern
        self.save(update_fields=["status", "progress", "result_path", "regex_pattern", "updated_at"])

    def mark_failed(self, error: str) -> None:
        self.status = self.Status.FAILED
        self.error_message = error
        self.save(update_fields=["status", "error_message", "updated_at"])

    def update_progress(self, pct: int) -> None:
        self.progress = max(0, min(100, pct))
        self.save(update_fields=["progress", "updated_at"])