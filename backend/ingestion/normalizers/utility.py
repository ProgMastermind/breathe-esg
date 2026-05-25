from decimal import Decimal
from ingestion.emission_factors import FACTORS


def normalize(parsed_row: dict) -> dict | None:
    usage_kwh = parsed_row.get("usage_kwh")
    if usage_kwh is None:
        return None

    factor_info = FACTORS["electricity_uk"]
    co2e_kg = Decimal(str(float(usage_kwh) * factor_info["factor"])) if usage_kwh else None

    # Use billing_end as the activity date (most common convention)
    activity_date = parsed_row.get("billing_end") or parsed_row.get("billing_start")

    address = parsed_row.get("service_address", "")
    meter = parsed_row.get("meter_id", "")
    account = parsed_row.get("account_number", "")
    desc = f"Electricity — {address or account}"
    if meter:
        desc += f" [Meter: {meter}]"

    billing_period_note = ""
    if parsed_row.get("billing_start") and parsed_row.get("billing_end"):
        billing_period_note = f"{parsed_row['billing_start']} to {parsed_row['billing_end']}"

    return {
        "source_type": "utility_electricity",
        "scope": "2",
        "activity_date": activity_date,
        "description": desc,
        "quantity": usage_kwh,
        "unit": "kWh",
        "co2e_kg": co2e_kg,
        "emission_factor": Decimal(str(factor_info["factor"])),
        "emission_factor_source": factor_info["source"],
        "_billing_period": billing_period_note,
        "_errors": parsed_row.get("_parse_errors", []),
        "_raw": parsed_row.get("_raw", {}),
        "_unit_note": parsed_row.get("_unit_note"),
    }
