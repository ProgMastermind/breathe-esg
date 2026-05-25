from django.contrib import admin
from .models import NormalizedRecord, ValidationFlag, AuditLog


class ValidationFlagInline(admin.TabularInline):
    model = ValidationFlag
    extra = 0
    readonly_fields = ("flag_type", "message", "severity", "created_at")


@admin.register(NormalizedRecord)
class NormalizedRecordAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "source_type", "scope", "activity_date", "quantity", "unit", "co2e_kg", "status", "is_locked")
    list_filter = ("status", "scope", "source_type", "is_locked")
    search_fields = ("description",)
    inlines = [ValidationFlagInline]
    readonly_fields = ("edit_history", "reviewed_at", "created_at")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "action", "changed_by", "changed_at")
    readonly_fields = ("before_state", "after_state", "changed_at")
