import os
import uuid
from django.conf import settings


def save_upload_to_disk(file) -> str:
    """
    Save an uploaded file to UPLOAD_DIR with a UUID-based filename.
    Returns the absolute path where the file was saved.
    """
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    _, ext = os.path.splitext(file.name.lower())
    filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, filename)

    with open(file_path, "wb") as dest:
        for chunk in file.chunks():
            dest.write(chunk)

    return file_path