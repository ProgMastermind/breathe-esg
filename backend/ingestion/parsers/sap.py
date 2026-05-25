"""
SAP flat-file parser for fuel and procurement data.

SAP exports via SE16N (data browser) or custom ABAP reports produce CSV/TSV files
with characteristics this parser handles:
- Column headers may be in German (Buchungsdatum, Werk, Menge, Mengeneinh)
- Dates in DD.MM.YYYY format
- SAP UoM codes (L, KG, M3, ST, GAL) rather than ISO units
- Decimal separator may be comma (German locale) or period
- Material descriptions can be German
- Some plants have only numeric codes; cost centers similarly opaque
"""

import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Iterator


# Column name aliases — maps SAP German/English headers to canonical names
COLUMN_MAP = {
    # Date
    "buchungsdatum": "posting_date",
    "belegdatum": "posting_date",
    "posting date": "posting_date",
    "posting_date": "posting_date",
    "date": "posting_date",
    "datum": "posting_date",

    # Plant / site
    "werk": "plant",
    "plant": "plant",
    "werks": "plant",

    # Material
    "material": "material_number",
    "material number": "material_number",
    "materialnr": "material_number",
    "matnr": "material_number",

    # Material description
    "materialbez": "material_description",
    "material description": "material_description",
    "materialbeschreibung": "material_description",
    "maktx": "material_description",
    "beschreibung": "material_description",

    # Material group
    "materialgruppe": "material_group",
    "material group": "material_group",
    "matkl": "material_group",
    "mat. group": "material_group",

    # Quantity
    "menge": "quantity",
    "quantity": "quantity",
    "erfmg": "quantity",
    "bwmng": "quantity",
    "bewegungsmenge": "quantity",

    # Unit of measure
    "mengeneinh": "unit",
    "mengeneinheit": "unit",
    "unit": "unit",
    "meins": "unit",
    "erfme": "unit",
    "bwein": "unit",

    # Cost center
    "kostl": "cost_center",
    "kostenstelle": "cost_center",
    "cost center": "cost_center",
    "cost_center": "cost_center",

    # Amount
    "betrag": "amount",
    "amount": "amount",
    "wrbtr": "amount",
    "dmbtr": "amount",

    # Currency
    "waehr": "currency",
    "währung": "currency",
    "currency": "currency",
    "waers": "currency",
    "hwaer": "currency",

    # Vendor
    "lieferant": "vendor",
    "vendor": "vendor",
    "lifnr": "vendor",

    # Company code
    "buchungskreis": "company_code",
    "company code": "company_code",
    "bukrs": "company_code",

    # Purchase order
    "bestellung": "purchase_order",
    "purchase order": "purchase_order",
    "ebeln": "purchase_order",
}


def _normalise_header(h: str) -> str:
    return h.strip().lower().replace(".", "").replace("-", " ")


def _parse_date(raw: str) -> str | None:
    raw = raw.strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _parse_decimal(raw: str) -> Decimal | None:
    raw = raw.strip().replace(" ", "")
    if not raw:
        return None
    # Handle German decimal comma: 1.234,56 → 1234.56
    if "," in raw and "." in raw:
        if raw.index(",") > raw.index("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def parse(file_content: bytes) -> Iterator[dict]:
    """
    Yields one dict per data row with canonical keys and a _parse_errors list.
    Caller is responsible for handling errors per row.
    """
    text = file_content.decode("utf-8-sig", errors="replace")  # handle BOM from Excel exports
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

        # Preserve all original fields too
        parsed["_raw"] = dict(row)

        # Parse date
        if "posting_date" in parsed:
            parsed["posting_date"] = _parse_date(parsed["posting_date"])
            if parsed["posting_date"] is None and row.get(
                next((k for k, v in header_map.items() if v == "posting_date"), ""), ""
            ):
                errors.append("Could not parse date")

        # Parse quantity
        if "quantity" in parsed:
            qty_raw = parsed["quantity"]
            parsed["quantity"] = _parse_decimal(qty_raw)
            if parsed["quantity"] is None and qty_raw:
                errors.append(f"Could not parse quantity: {qty_raw!r}")

        # Parse amount
        if "amount" in parsed:
            parsed["amount"] = _parse_decimal(parsed["amount"])

        parsed["_parse_errors"] = errors
        yield parsed
