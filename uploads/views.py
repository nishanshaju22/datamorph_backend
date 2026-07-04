import os
import shutil
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser

from .models import Upload
from .serializers import UploadSerializer, UploadCreateSerializer
from .validators import validate_upload_file
from .storage import save_upload_to_disk
from rest_framework.exceptions import NotFound
from processing.tasks import inspect_upload_task


class UploadListCreateView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        uploads = Upload.objects.all().order_by('-created_at')
        return Response(UploadSerializer(uploads, many=True).data)

    def post(self, request):
        # Validate incoming request
        create_serializer = UploadCreateSerializer(data=request.data)
        create_serializer.is_valid(raise_exception=True)
        file = create_serializer.validated_data["file"]

        # Validate file type
        mime_type = validate_upload_file(file)

        # Save to disk
        file_path = save_upload_to_disk(file)

        # Create database record
        upload = Upload.objects.create(
            session_key = "annoymous"
            original_name = file.name,
            file_path = file_path,
            file_size = file.size,
            mime_type = mime_type,
            status = Upload.Status.PENDING,
        )
        
        
        print("UPLOAD SESSION:", request.session.session_key)
        print("UPLOAD ID:", upload.id)
        print("UPLOAD DB SESSION:", upload.session_key)

        # Dispatch background task to inspect the file
        inspect_upload_task.apply_async(args=[str(upload.id)], countdown=2)
        
        return Response(
            UploadSerializer(upload).data,
            status=status.HTTP_201_CREATED
        )

    def _get_owned_upload(self, request, pk):
        try:
            return Upload.objects.get(pk=pk)
        except Upload.DoesNotExist:
            raise NotFound("Upload not found.")


class UploadDetailView(APIView):

    def get(self, request, pk):
        upload = self._get_owned_upload(request, pk)
        return Response(UploadSerializer(upload).data)
    
    def delete(self, request, pk):
        upload = self._get_owned_upload(request, pk)
        
        print("GET SESSION:", request.session.session_key)
        print("LOOKING FOR:", pk)

        print(
            "EXISTS:",
            Upload.objects.filter(
                pk=pk,
            ).exists()
        )


        # Cancel any running jobs first
        for job in upload.jobs.filter(status__in=["QUEUED", "RUNNING"]):
            if job.celery_task_id:
                from celery.result import AsyncResult
                AsyncResult(job.celery_task_id).revoke(terminate=True)

        # Delete file from disk
        if os.path.exists(upload.file_path):
            os.remove(upload.file_path)

        # Delete result files
        for job in upload.jobs.all():
            if job.result_path and os.path.exists(job.result_path):
                shutil.rmtree(job.result_path, ignore_errors=True)

        # Delete DB record
        upload.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)

    def _get_owned_upload(self, request, pk):
        try:
            print(
                "UPLOAD IN DB:",
                Upload.objects.filter(pk=pk).values("id", "session_key")
            )
            return Upload.objects.get(
                pk=pk,
            )
        except Upload.DoesNotExist:
            raise NotFound("Upload not found.")


class UploadPreviewView(APIView):

    def get(self, request, pk):
        return Response({"detail": "not implemented yet"}, status=status.HTTP_200_OK)