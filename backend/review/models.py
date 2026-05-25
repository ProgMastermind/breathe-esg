from django.db import models
from django.conf import settings
from django.utils import timezone
from core.models import Tenant
from ingestion.models import IngestionBatch, RawRecord, SourceType


class Scope(models.TextChoices):
    SCOPE_1 = "1", "Scope 1 (Direct)"
    SCOPE_2 = "2", "Scope 2 (Electricity)"
    SCOPE_3 = "3", "Scope 3 (Value Chain)"


class RecordStatus(models.TextChoices):
    PENDING = "pending", "Pending Review"
    FLAGGED = "flagged", "Flagged"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class NormalizedRecord(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="records")
    raw_record = models.OneToOneField(
        RawRecord, on_delete=models.CASCADE, related_name="normalized", null=True, blank=True
    )
    batch = models.ForeignKey(IngestionBatch, on_delete=models.CASCADE, related_name="records")
    source_type = models.CharField(max_length=30, choices=SourceType.choices)
    scope = models.CharField(max_length=1, choices=Scope.choices)

    activity_date = models.DateField(null=True, blank=True)
    description = models.CharField(max_length=500, blank=True)

    quantity = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    unit = models.CharField(max_length=50, blank=True)

    co2e_kg = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    emission_factor = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    emission_factor_source = models.CharField(max_length=200, blank=True)

    status = models.CharField(max_length=20, choices=RecordStatus.choices, default=RecordStatus.PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_records"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    is_locked = models.BooleanField(default=False)
    analyst_notes = models.TextField(blank=True)
    edit_history = models.JSONField(default=list)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-activity_date", "-created_at"]

    def __str__(self):
        return f"{self.get_source_type_display()} | {self.activity_date} | {self.quantity} {self.unit}"

    def approve(self, user):
        self.status = RecordStatus.APPROVED
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        self.is_locked = True
        self.save()

    def reject(self, user, notes=""):
        self.status = RecordStatus.REJECTED
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        if notes:
            self.analyst_notes = notes
        self.save()


class FlagType(models.TextChoices):
    MISSING_REQUIRED_FIELD = "missing_required_field", "Missing Required Field"
    FUTURE_DATE = "future_date", "Future Date"
    NEGATIVE_QUANTITY = "negative_quantity", "Negative Quantity"
    OUTLIER_HIGH = "outlier_high", "Unusually High Value"
    DUPLICATE_RECORD = "duplicate_record", "Possible Duplicate"
    UTILITY_LONG_BILLING_PERIOD = "utility_long_billing_period", "Long Billing Period"
    TRAVEL_MISSING_DISTANCE = "travel_missing_distance", "Missing Distance"
    UNIT_CONVERSION_ASSUMPTION = "unit_conversion_assumption", "Unit Conversion Assumed"
    ZERO_QUANTITY = "zero_quantity", "Zero Quantity"


class FlagSeverity(models.TextChoices):
    ERROR = "error", "Error"
    WARN = "warn", "Warning"
    INFO = "info", "Info"


class ValidationFlag(models.Model):
    record = models.ForeignKey(NormalizedRecord, on_delete=models.CASCADE, related_name="flags")
    flag_type = models.CharField(max_length=50, choices=FlagType.choices)
    message = models.TextField()
    severity = models.CharField(max_length=10, choices=FlagSeverity.choices)
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.severity.upper()}: {self.message[:60]}"


class AuditLog(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="audit_logs")
    record = models.ForeignKey(
        NormalizedRecord, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs"
    )
    action = models.CharField(max_length=100)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="audit_actions"
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    before_state = models.JSONField(default=dict)
    after_state = models.JSONField(default=dict)

    class Meta:
        ordering = ["-changed_at"]

    def __str__(self):
        return f"{self.action} by {self.changed_by} at {self.changed_at}"
