"""
Utility electricity data parser.

Handles portal CSV exports from utilities like PG&E, ConEd, Eversource, etc.
Billing periods don't align to calendar months (28-35 days is normal).
Some large commercial meters report in MWh; most report in kWh.
"""

import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Iterator


COLUMN_MAP = {
    # Account
    "account_number": "account_number",
    "account number": "account_number",
    "account": "account_number",
    "acct_number": "account_number",
    "account no": "account_number",

    # Meter
    "meter_id": "meter_id",
    "meter id": "meter_id",
    "meter": "meter_id",
    "meter_number": "meter_id",
    "mpan": "meter_id",
    "meter serial": "meter_id",

    # Service address
    "service_address": "service_address",
    "service address": "service_address",
    "address": "service_address",
    "premise_address": "service_address",
    "site": "service_address",

    # Billing period
    "billing_start": "billing_start",
    "billing start": "billing_start",
    "period_start": "billing_start",
    "service_start": "billing_start",
    "start_date": "billing_start",
    "from_date": "billing_start",

    "billing_end": "billing_end",
    "billing end": "billing_end",
    "period_end": "billing_end",
    "service_end": "billing_end",
    "end_date": "billing_end",
    "to_date": "billing_end",
    "through_date": "billing_end",

    # Usage
    "usage_kwh": "usage_kwh",
    "usage (kwh)": "usage_kwh",
    "usage_mwh": "usage_mwh",
    "usage (mwh)": "usage_mwh",
    "consumption_kwh": "usage_kwh",
    "consumption (kwh)": "usage_kwh",
    "kwh": "usage_kwh",
    "mwh": "usage_mwh",
    "electric usage (kwh)": "usage_kwh",
    "total usage (kwh)": "usage_kwh",
    "total_kwh": "usage_kwh",
    "usage": "usage_kwh",

    # Peak demand
    "peak_demand_kw": "peak_demand_kw",
    "peak demand (kw)": "peak_demand_kw",
    "demand_kw": "peak_demand_kw",
    "demand (kw)": "peak_demand_kw",
    "max demand": "peak_demand_kw",

    # Tariff
    "tariff_code": "tariff_code",
    "tariff": "tariff_code",
    "rate_schedule": "tariff_code",
    "rate": "tariff_code",
    "rate_code": "tariff_code",

    # Cost
    "total_charges_gbp": "total_cost",
    "total_charges_usd": "total_cost",
    "total charges": "total_cost",
    "amount": "total_cost",
    "total_amount": "total_cost",
    "total_cost": "total_cost",
    "bill_amount": "total_cost",
    "charges": "total_cost",
}


def _normalise_header(h: str) -> str:
    return h.strip().lower()


def _parse_date(raw: str) -> str | None:
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%d-%m-%Y", "%m-%d-%Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _parse_decimal(raw: str) -> Decimal | None:
    raw = str(raw).strip().replace(",", "").replace("$", "").replace("£", "").replace("€", "")
    if not raw:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def parse(file_content: bytes) -> Iterator[dict]:
    text = file_content.decode("utf-8-sig", errors="replace")
    dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)

    raw_headers = reader.fieldnames or []
    header_map = {}
    for raw_h in raw_headers:
        canonical = COLUMN_MAP.get(_normalise_header(raw_h))
        if canonical:
            header_map[raw_h] = canonical

    for row in reader:
        parsed: dict = {}
        errors: list[str] = []

        for raw_h, canonical in header_map.items():
            parsed[canonical] = row.get(raw_h, "").strip()

        parsed["_raw"] = dict(row)

        for date_field in ("billing_start", "billing_end"):
            if date_field in parsed:
                parsed[date_field] = _parse_date(parsed[date_field])
                if parsed[date_field] is None:
                    errors.append(f"Could not parse {date_field}")

        # Normalise usage to kWh
        usage_kwh = None
        if "usage_kwh" in parsed and parsed["usage_kwh"]:
            usage_kwh = _parse_decimal(parsed["usage_kwh"])
            parsed["usage_kwh"] = usage_kwh
            parsed["_unit"] = "kWh"
        elif "usage_mwh" in parsed and parsed["usage_mwh"]:
            mwh = _parse_decimal(parsed["usage_mwh"])
            if mwh is not None:
                usage_kwh = mwh * 1000
                parsed["usage_kwh"] = usage_kwh
                parsed["_unit"] = "kWh"
                parsed["_unit_note"] = "Converted from MWh"

        if usage_kwh is None:
            errors.append("No usage data found")

        parsed["peak_demand_kw"] = _parse_decimal(parsed.get("peak_demand_kw", ""))
        parsed["total_cost"] = _parse_decimal(parsed.get("total_cost", ""))

        parsed["_parse_errors"] = errors
        yield parsed
