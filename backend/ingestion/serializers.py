from rest_framework import serializers
from .models import IngestionBatch, RawRecord


class IngestionBatchSerializer(serializers.ModelSerializer):
    source_type_display = serializers.CharField(source="get_source_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    ingested_by_name = serializers.SerializerMethodField()

    class Meta:
        model = IngestionBatch
        fields = (
            "id", "source_type", "source_type_display", "file_name",
            "status", "status_display", "row_count", "error_count",
            "ingested_by_name", "ingested_at", "notes",
        )

    def get_ingested_by_name(self, obj):
        if obj.ingested_by:
            return obj.ingested_by.get_full_name() or obj.ingested_by.username
        return None


class RawRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawRecord
        fields = ("id", "row_number", "raw_data", "parse_error", "created_at")
