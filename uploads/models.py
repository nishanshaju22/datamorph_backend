import uuid
from django.db import models


class Upload(models.Model):
    """
    Represents a file uploaded by a user session
    Stores metadata about the file
    file lives on disk
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        READY = "READY", "Ready"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_key = models.CharField(max_length=40, db_index=True)
    original_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=1024)
    file_size = models.PositiveBigIntegerField(default=0)
    mime_type = models.CharField(max_length=128, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    row_count = models.PositiveBigIntegerField(null=True, blank=True)
    column_meta = models.JSONField(default=list)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["session_key", "created_at"])]

    def __str__(self):
        return f"Upload({self.original_name}, {self.status})"