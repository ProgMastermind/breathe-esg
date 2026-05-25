from django.db import models
from django.conf import settings
from core.models import Tenant


class SourceType(models.TextChoices):
    SAP_FUEL = "sap_fuel", "SAP Fuel"
    SAP_PROCUREMENT = "sap_procurement", "SAP Procurement"
    UTILITY_ELECTRICITY = "utility_electricity", "Utility Electricity"
    TRAVEL_FLIGHT = "travel_flight", "Travel Flight"
    TRAVEL_HOTEL = "travel_hotel", "Travel Hotel"
    TRAVEL_GROUND = "travel_ground", "Travel Ground"


class BatchStatus(models.TextChoices):
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class IngestionBatch(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="batches")
    source_type = models.CharField(max_length=30, choices=SourceType.choices)
    file_name = models.CharField(max_length=500)
    status = models.CharField(max_length=20, choices=BatchStatus.choices, default=BatchStatus.PROCESSING)
    row_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    ingested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    ingested_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-ingested_at"]

    def __str__(self):
        return f"{self.get_source_type_display()} — {self.file_name} ({self.ingested_at:%Y-%m-%d})"


class RawRecord(models.Model):
    batch = models.ForeignKey(IngestionBatch, on_delete=models.CASCADE, related_name="raw_records")
    row_number = models.IntegerField()
    raw_data = models.JSONField()
    parse_error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["row_number"]

    def __str__(self):
        return f"Row {self.row_number} of batch {self.batch_id}"
