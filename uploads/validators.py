import os
import magic
from django.conf import settings
from rest_framework.exceptions import ValidationError


ALLOWED_MIME_TYPES = {
    "text/csv": ".csv",
    "application/csv": ".csv",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}


def validate_upload_file(file) -> str:
    """
    Validate an uploaded file by extension AND magic bytes.
    Returns the detected MIME type on success.
    Raises ValidationError on failure.
    """
    
    # Check extension
    _, ext = os.path.splitext(file.name.lower())
    if ext not in settings.ALLOWED_UPLOAD_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file type '{ext}'. "
            f"Allowed: {', '.join(settings.ALLOWED_UPLOAD_EXTENSIONS)}"
        )

    # Check actual file content usin magic bytes
    header = file.read(2048)
    file.seek(0)
    mime_type = magic.from_buffer(header, mime=True)

    if mime_type not in ALLOWED_MIME_TYPES:
        raise ValidationError(
            f"File content does not match a supported type. Detected: {mime_type}"
        )

    return mime_type