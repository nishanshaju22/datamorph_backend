from rest_framework import serializers
from .models import Job


class JobSerializer(serializers.ModelSerializer):
    upload = serializers.UUIDField(source='upload.id', read_only=True)

    class Meta:
        model = Job
        fields = [
            "id",
            "upload",
            "nl_prompt",
            "target_columns",
            "replacement",
            "regex_pattern",
            "status",
            "progress",
            "error_message",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class JobCreateSerializer(serializers.Serializer):
    upload_id = serializers.UUIDField()
    nl_prompt = serializers.CharField(max_length=1000)
    target_columns = serializers.ListField(
        child=serializers.CharField(),
        min_length=1,
    )
    replacement = serializers.CharField(max_length=1024, allow_blank=True)