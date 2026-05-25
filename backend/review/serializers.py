from rest_framework import serializers
from .models import NormalizedRecord, ValidationFlag, AuditLog


class ValidationFlagSerializer(serializers.ModelSerializer):
    flag_type_display = serializers.CharField(source="get_flag_type_display", read_only=True)

    class Meta:
        model = ValidationFlag
        fields = ("id", "flag_type", "flag_type_display", "message", "severity", "resolved", "created_at")


class NormalizedRecordSerializer(serializers.ModelSerializer):
    source_type_display = serializers.CharField(source="get_source_type_display", read_only=True)
    scope_display = serializers.CharField(source="get_scope_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    flags = ValidationFlagSerializer(many=True, read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()
    raw_data = serializers.SerializerMethodField()

    class Meta:
        model = NormalizedRecord
        fields = (
            "id", "batch", "source_type", "source_type_display",
            "scope", "scope_display", "activity_date", "description",
            "quantity", "unit", "co2e_kg", "emission_factor", "emission_factor_source",
            "status", "status_display", "is_locked",
            "analyst_notes", "edit_history", "flags",
            "reviewed_by_name", "reviewed_at", "created_at", "raw_data",
        )
        read_only_fields = (
            "id", "batch", "source_type", "scope", "activity_date",
            "quantity", "unit", "co2e_kg", "emission_factor", "emission_factor_source",
            "is_locked", "edit_history", "reviewed_by_name", "reviewed_at", "created_at",
            "flags", "raw_data",
        )

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name() or obj.reviewed_by.username
        return None

    def get_raw_data(self, obj):
        if obj.raw_record:
            return obj.raw_record.raw_data
        return None


class AuditLogSerializer(serializers.ModelSerializer):
    changed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = ("id", "action", "changed_by_name", "changed_at", "before_state", "after_state")

    def get_changed_by_name(self, obj):
        if obj.changed_by:
            return obj.changed_by.get_full_name() or obj.changed_by.username
        return "System"
