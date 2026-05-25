"""
Corporate travel parser for Concur-style expense CSV exports.

Key limitation of standard Concur exports: no distance column. We derive flight
distance from origin/destination IATA codes using the haversine formula with a
built-in airport coordinate table (~500 major airports).

Cabin class is often missing or inconsistent; we default to economy.
Currency may be mixed (USD/GBP/EUR); we record the original and don't convert.
"""

import csv
import io
import math
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Iterator


# IATA code → (lat, lon) for ~120 major airports used in business travel
# Coordinates are approximate (city/airport level), sufficient for GCD distance
AIRPORT_COORDS: dict[str, tuple[float, float]] = {
    "LHR": (51.477, -0.461), "LGW": (51.148, -0.190), "MAN": (53.354, -2.275),
    "EDI": (55.950, -3.373), "BHX": (52.453, -1.748), "DUB": (53.421, -6.270),
    "AMS": (52.308, 4.764), "CDG": (49.009, 2.548), "FRA": (50.033, 8.571),
    "MUC": (48.354, 11.786), "ZRH": (47.458, 8.548), "VIE": (48.110, 16.570),
    "BRU": (50.901, 4.484), "ARN": (59.652, 17.919), "CPH": (55.618, 12.656),
    "OSL": (60.193, 11.100), "HEL": (60.317, 24.963), "LIS": (38.774, -9.134),
    "MAD": (40.472, -3.561), "BCN": (41.297, 2.078), "FCO": (41.800, 12.239),
    "MXP": (45.630, 8.723), "ATH": (37.936, 23.945), "IST": (40.976, 28.815),
    "DXB": (25.253, 55.365), "AUH": (24.433, 54.651), "DOH": (25.273, 51.608),
    "SIN": (1.359, 103.989), "HKG": (22.308, 113.918), "NRT": (35.765, 140.386),
    "PEK": (40.080, 116.585), "PVG": (31.143, 121.805), "BOM": (19.089, 72.868),
    "DEL": (28.556, 77.100), "SYD": (-33.946, 151.177), "MEL": (-37.673, 144.843),
    "JNB": (-26.133, 28.242), "NBO": (-1.319, 36.927), "CAI": (30.122, 31.406),
    "LAX": (33.943, -118.408), "JFK": (40.640, -73.778), "ORD": (41.980, -87.905),
    "ATL": (33.637, -84.428), "DFW": (32.897, -97.038), "DEN": (39.856, -104.674),
    "SFO": (37.619, -122.375), "SEA": (47.449, -122.311), "LAS": (36.080, -115.152),
    "MIA": (25.796, -80.287), "BOS": (42.366, -71.010), "IAD": (38.953, -77.456),
    "IAH": (29.984, -95.341), "PHX": (33.436, -112.011), "MSP": (44.882, -93.222),
    "DTW": (42.213, -83.353), "EWR": (40.690, -74.174), "PHL": (39.872, -75.241),
    "CLT": (35.214, -80.943), "SLC": (40.788, -111.978), "PDX": (45.589, -122.593),
    "MDW": (41.786, -87.752), "BWI": (39.177, -76.668), "TPA": (27.976, -82.533),
    "MCO": (28.429, -81.308), "YYZ": (43.677, -79.631), "YVR": (49.195, -123.184),
    "YUL": (45.470, -73.741), "MEX": (19.436, -99.072), "GRU": (-23.435, -46.473),
    "EZE": (-34.822, -58.536), "SCL": (-33.393, -70.786), "BOG": (4.702, -74.147),
    "LIM": (-12.022, -77.114),
}


COLUMN_MAP = {
    "employeeid": "employee_id",
    "employee id": "employee_id",
    "employee_id": "employee_id",
    "emp id": "employee_id",

    "reportname": "report_name",
    "report name": "report_name",
    "report_name": "report_name",
    "report id": "report_name",
    "reportid": "report_name",

    "expensetype": "expense_type",
    "expense type": "expense_type",
    "expense_type": "expense_type",
    "category": "expense_type",
    "type": "expense_type",

    "merchant": "merchant",
    "vendor": "merchant",
    "description": "merchant",

    "departurecode": "departure_code",
    "departure code": "departure_code",
    "departure_code": "departure_code",
    "origin": "departure_code",
    "from": "departure_code",

    "arrivalcode": "arrival_code",
    "arrival code": "arrival_code",
    "arrival_code": "arrival_code",
    "destination": "arrival_code",
    "to": "arrival_code",

    "amount": "amount",
    "total": "amount",
    "cost": "amount",

    "currency": "currency",
    "ccy": "currency",

    "expensedate": "expense_date",
    "expense date": "expense_date",
    "expense_date": "expense_date",
    "transaction date": "expense_date",
    "date": "expense_date",

    "cabinclass": "cabin_class",
    "cabin class": "cabin_class",
    "cabin_class": "cabin_class",
    "class": "cabin_class",

    "nights": "nights",
    "room nights": "nights",
    "no. of nights": "nights",

    "notes": "notes",
    "memo": "notes",
    "comment": "notes",
    "comments": "notes",
}

EXPENSE_TYPE_MAP = {
    # → flight
    "air": "flight", "air travel": "flight", "flight": "flight",
    "airfare": "flight", "airline": "flight", "aviation": "flight",

    # → hotel
    "hotel": "hotel", "lodging": "hotel", "accommodation": "hotel",
    "hotel/motel": "hotel",

    # → car
    "car rental": "car", "car hire": "car", "rental car": "car",
    "vehicle rental": "car",

    # → taxi
    "taxi": "taxi", "cab": "taxi", "rideshare": "taxi",
    "uber": "taxi", "lyft": "taxi", "ground transport": "taxi",

    # → rail
    "rail": "rail", "train": "rail", "railway": "rail",
    "amtrak": "rail", "eurostar": "rail",
}


def _normalise_header(h: str) -> str:
    return h.strip().lower()


def _parse_date(raw: str) -> str | None:
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%d-%m-%Y", "%m-%d-%Y", "%d.%m.%Y"):
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


def _haversine_km(coord1: tuple[float, float], coord2: tuple[float, float]) -> float:
    lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
    lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def _extract_iata_codes(text: str) -> tuple[str | None, str | None]:
    """Extract origin/destination IATA codes from a free-text field like 'ORD-LHR' or 'Chicago (ORD) to London (LHR)'."""
    codes = re.findall(r"\b([A-Z]{3})\b", text.upper())
    valid = [c for c in codes if c in AIRPORT_COORDS]
    if len(valid) >= 2:
        return valid[0], valid[1]
    return None, None


def _classify_expense(raw_type: str) -> str:
    return EXPENSE_TYPE_MAP.get(raw_type.strip().lower(), "other")


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

        parsed["expense_date"] = _parse_date(parsed.get("expense_date", ""))
        if not parsed["expense_date"]:
            errors.append("Could not parse expense_date")

        parsed["amount"] = _parse_decimal(parsed.get("amount", ""))
        parsed["nights"] = _parse_decimal(parsed.get("nights", ""))

        # Classify expense type
        raw_expense_type = parsed.get("expense_type", "")
        parsed["expense_category"] = _classify_expense(raw_expense_type)

        # For flights, derive distance from IATA codes
        origin = parsed.get("departure_code", "").upper().strip()
        dest = parsed.get("arrival_code", "").upper().strip()

        # If not explicitly in columns, try to parse from merchant/notes
        if not (origin and dest):
            origin_candidate, dest_candidate = _extract_iata_codes(
                parsed.get("merchant", "") + " " + parsed.get("notes", "")
            )
            if origin_candidate and not origin:
                origin = origin_candidate
            if dest_candidate and not dest:
                dest = dest_candidate

        parsed["departure_code"] = origin or None
        parsed["arrival_code"] = dest or None
        parsed["distance_km"] = None
        parsed["_distance_source"] = None

        if parsed["expense_category"] == "flight" and origin and dest:
            c1 = AIRPORT_COORDS.get(origin)
            c2 = AIRPORT_COORDS.get(dest)
            if c1 and c2:
                parsed["distance_km"] = round(_haversine_km(c1, c2))
                parsed["_distance_source"] = "haversine"
            else:
                errors.append(f"Airport code not found: {origin} or {dest}")

        parsed["_parse_errors"] = errors
        yield parsed
