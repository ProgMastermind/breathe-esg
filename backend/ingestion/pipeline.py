"""
Orchestrates the full parse → normalize → validate → persist pipeline.
Called synchronously on upload (no Celery — deliberate tradeoff documented).
"""

from ingestion.models import IngestionBatch, RawRecord, BatchStatus
from ingestion.parsers import sap as sap_parser
from ingestion.parsers import utility as utility_parser
from ingestion.parsers import travel as travel_parser
from ingestion.normalizers import sap as sap_normalizer
from ingestion.normalizers import utility as utility_normalizer
from ingestion.normalizers import travel as travel_normalizer
from ingestion import validators
from review.models import NormalizedRecord, ValidationFlag


PARSERS = {
    "sap_fuel": sap_parser,
    "sap_procurement": sap_parser,
    "utility_electricity": utility_parser,
    "travel_flight": travel_parser,
    "travel_hotel": travel_parser,
    "travel_ground": travel_parser,
}

NORMALIZERS = {
    "sap_fuel": sap_normalizer,
    "sap_procurement": sap_normalizer,
    "utility_electricity": utility_normalizer,
    "travel_flight": travel_normalizer,
    "travel_hotel": travel_normalizer,
    "travel_ground": travel_normalizer,
}


def run(batch: IngestionBatch, file_content: bytes):
    parser = PARSERS[batch.source_type]
    normalizer = NORMALIZERS[batch.source_type]

    row_count = 0
    error_count = 0
    normalized_records = []

    try:
        for i, parsed_row in enumerate(parser.parse(file_content)):
            row_count += 1
            parse_errors = parsed_row.get("_parse_errors", [])

            raw_record = RawRecord.objects.create(
                batch=batch,
                row_number=i + 1,
                raw_data=parsed_row.get("_raw", parsed_row),
                parse_error="\n".join(parse_errors) if parse_errors else None,
            )

            if any(e for e in parse_errors if "Could not parse" in e and "date" in e.lower()):
                error_count += 1
                continue

            norm = normalizer.normalize(parsed_row)
            if norm is None:
                continue

            norm_errors = norm.pop("_errors", [])
            norm.pop("_raw", None)
            norm.pop("_distance_source", None)
            norm.pop("_unit_note", None)
            norm.pop("_billing_period", None)
            norm.pop("_fuel_type", None)
            norm.pop("_unit_assumption", None)
            # CharField fields cannot be None — coerce to empty string
            if norm.get("unit") is None:
                norm["unit"] = ""
            if norm.get("emission_factor_source") is None:
                norm["emission_factor_source"] = ""
            if norm.get("description") is None:
                norm["description"] = ""

            record = NormalizedRecord.objects.create(
                tenant=batch.tenant,
                raw_record=raw_record,
                batch=batch,
                **norm,
            )

            # Determine initial status — flagged if there are errors in norm_errors
            flag_rows = []
            for (flag_type, message, severity) in validators.validate(record):
                flag_rows.append(ValidationFlag(
                    record=record, flag_type=flag_type, message=message, severity=severity
                ))
            for err_msg in norm_errors:
                flag_rows.append(ValidationFlag(
                    record=record,
                    flag_type="unit_conversion_assumption",
                    message=err_msg,
                    severity="info",
                ))

            if flag_rows:
                ValidationFlag.objects.bulk_create(flag_rows)
                has_error = any(f.severity == "error" for f in flag_rows)
                record.status = "flagged" if has_error else "pending"
                record.save(update_fields=["status"])

            normalized_records.append(record)

        # Post-processing: outlier and duplicate checks across the full batch
        if normalized_records:
            existing_qs = NormalizedRecord.objects.filter(tenant=batch.tenant)
            extra_flags = []
            for record in normalized_records:
                extra_flags += validators.check_outlier(record, existing_qs)
                extra_flags += validators.check_duplicate(record, existing_qs)

            if extra_flags:
                bulk_flags = []
                for record in normalized_records:
                    rec_outlier = validators.check_outlier(record, existing_qs)
                    rec_dup = validators.check_duplicate(record, existing_qs)
                    for (ft, msg, sev) in rec_outlier + rec_dup:
                        bulk_flags.append(ValidationFlag(record=record, flag_type=ft, message=msg, severity=sev))
                        if record.status == "pending":
                            record.status = "flagged"
                ValidationFlag.objects.bulk_create(bulk_flags)
                NormalizedRecord.objects.bulk_update(
                    [r for r in normalized_records if r.status == "flagged"], ["status"]
                )

        batch.row_count = row_count
        batch.error_count = error_count
        batch.status = BatchStatus.COMPLETED
        batch.save()

    except Exception as exc:
        batch.status = BatchStatus.FAILED
        batch.notes = str(exc)
        batch.save()
        raise
