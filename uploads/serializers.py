from rest_framework import serializers
from .models import Upload


class UploadSerializer(serializers.ModelSerializer):
    """Serializer for returning upload metadata to the client."""

    class Meta:
        model  = Upload
        fields = [
            "id",
            "original_name",
            "file_size",
            "mime_type",
            "status",
            "row_count",
            "column_meta",
            "created_at",
        ]
        read_only_fields = fields


class UploadCreateSerializer(serializers.Serializer):
    """Serializer for validating the incoming upload request."""
    file = serializers.FileField()