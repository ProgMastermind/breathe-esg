"""
Post-normalization validation rules. Each rule receives a NormalizedRecord instance
and returns a list of (flag_type, message, severity) tuples.
"""

from datetime import date
from decimal import Decimal
from django.utils import timezone


def validate(record) -> list[tuple[str, str, str]]:
    flags = []
    flags.extend(_check_missing_fields(record))
    flags.extend(_check_future_date(record))
    flags.extend(_check_negative_or_zero(record))
    flags.extend(_check_utility_billing_period(record))
    flags.extend(_check_travel_missing_distance(record))
    return flags


def _check_missing_fields(record) -> list:
    flags = []
    if record.activity_date is None:
        flags.append(("missing_required_field", "Activity date is missing.", "error"))
    if record.quantity is None and record.source_type in (
        "sap_fuel", "utility_electricity", "travel_flight", "travel_hotel"
    ):
        flags.append(("missing_required_field", "Quantity is missing.", "error"))
    if not record.unit and record.quantity is not None:
        flags.append(("missing_required_field", "Unit of measure is missing.", "warn"))
    return flags


def _check_future_date(record) -> list:
    if not record.activity_date:
        return []
    try:
        activity = record.activity_date if isinstance(record.activity_date, date) else date.fromisoformat(str(record.activity_date))
        if activity > date.today():
            return [("future_date", f"Activity date {activity} is in the future.", "warn")]
    except (ValueError, TypeError):
        pass
    return []


def _check_negative_or_zero(record) -> list:
    flags = []
    if record.quantity is not None:
        if record.quantity < Decimal("0"):
            flags.append(("negative_quantity", f"Quantity is negative: {record.quantity}.", "error"))
        elif record.quantity == Decimal("0"):
            flags.append(("zero_quantity", "Quantity is zero — possible data entry error.", "warn"))
    return flags


def _check_utility_billing_period(record) -> list:
    if record.source_type != "utility_electricity":
        return []
    raw = record.raw_record.raw_data if record.raw_record else {}
    start = raw.get("billing_start")
    end = raw.get("billing_end")
    if start and end:
        try:
            from datetime import date as d
            s = d.fromisoformat(start)
            e = d.fromisoformat(end)
            days = (e - s).days
            if days > 35:
                return [("utility_long_billing_period",
                         f"Billing period is {days} days (expected ≤35). Check for duplicate or merged bills.",
                         "warn")]
        except (ValueError, TypeError):
            pass
    return []


def _check_travel_missing_distance(record) -> list:
    if record.source_type == "travel_flight" and record.co2e_kg is None:
        return [("travel_missing_distance",
                 "Flight CO2e not calculated because distance could not be derived from airport codes.",
                 "warn")]
    return []


def check_outlier(record, tenant_records_qs) -> list[tuple[str, str, str]]:
    """
    Statistical outlier check. Requires queryset of existing records for same source_type.
    Uses mean + 3σ threshold.
    """
    from django.db.models import Avg, StdDev
    if record.quantity is None:
        return []
    stats = tenant_records_qs.filter(
        source_type=record.source_type, quantity__isnull=False
    ).aggregate(avg=Avg("quantity"), std=StdDev("quantity"))
    avg = stats["avg"]
    std = stats["std"]
    if avg is not None and std is not None and std > 0:
        threshold = avg + 3 * std
        if float(record.quantity) > threshold:
            return [("outlier_high",
                     f"Quantity {record.quantity} {record.unit} exceeds mean+3σ threshold ({threshold:.2f}). Verify.",
                     "warn")]
    return []


def check_duplicate(record, tenant_records_qs) -> list[tuple[str, str, str]]:
    exists = tenant_records_qs.filter(
        source_type=record.source_type,
        activity_date=record.activity_date,
        quantity=record.quantity,
        unit=record.unit,
    ).exclude(pk=record.pk).exists()
    if exists:
        return [("duplicate_record",
                 f"A record with the same source, date, and quantity already exists. Possible duplicate.",
                 "warn")]
    return []
