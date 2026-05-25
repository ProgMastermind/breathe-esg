from decimal import Decimal
from ingestion.emission_factors import FACTORS


SOURCE_TYPE_MAP = {
    "flight": "travel_flight",
    "hotel": "travel_hotel",
    "car": "travel_ground",
    "taxi": "travel_ground",
    "rail": "travel_ground",
    "other": "travel_ground",
}


def normalize(parsed_row: dict) -> dict | None:
    category = parsed_row.get("expense_category", "other")
    source_type = SOURCE_TYPE_MAP.get(category, "travel_ground")

    quantity = None
    unit = None
    co2e_kg = None
    factor_info = None
    errors = list(parsed_row.get("_parse_errors", []))

    if category == "flight":
        distance_km = parsed_row.get("distance_km")
        if distance_km:
            threshold_km = 3700
            cabin = (parsed_row.get("cabin_class") or "economy").lower()
            if "business" in cabin or "biz" in cabin:
                factor_key = "flight_short_haul_business" if distance_km < threshold_km else "flight_long_haul_business"
            else:
                factor_key = "flight_short_haul_economy" if distance_km < threshold_km else "flight_long_haul_economy"

            factor_info = FACTORS[factor_key]
            quantity = Decimal(str(distance_km))
            unit = "passenger_km"
            co2e_kg = Decimal(str(distance_km * factor_info["factor"]))
        else:
            errors.append("Flight distance unknown — CO2e not calculated")

        origin = parsed_row.get("departure_code") or ""
        dest = parsed_row.get("arrival_code") or ""
        desc = f"Flight: {origin}→{dest}"
        if parsed_row.get("merchant"):
            desc += f" ({parsed_row['merchant']})"

    elif category == "hotel":
        nights = parsed_row.get("nights")
        if nights:
            factor_info = FACTORS["hotel_uk"]
            quantity = nights
            unit = "room_nights"
            co2e_kg = Decimal(str(float(nights) * factor_info["factor"]))
        else:
            errors.append("Hotel nights not found — CO2e not calculated")
        desc = f"Hotel: {parsed_row.get('merchant', 'Unknown')}"

    elif category == "car":
        # Concur car rental rarely provides distance; use amount as proxy only for flagging
        factor_info = FACTORS["car_rental_average"]
        desc = f"Car Rental: {parsed_row.get('merchant', 'Unknown')}"
        errors.append("Car rental distance not provided — CO2e not calculated")

    elif category == "taxi":
        factor_info = FACTORS["taxi"]
        desc = f"Ground Transport: {parsed_row.get('merchant', 'Unknown')}"
        errors.append("Taxi distance not provided — CO2e not calculated")

    elif category == "rail":
        factor_info = FACTORS["rail"]
        desc = f"Rail: {parsed_row.get('merchant', 'Unknown')}"
        errors.append("Rail distance not provided — CO2e not calculated")

    else:
        desc = parsed_row.get("merchant", "Unknown expense")
        errors.append("Unrecognised expense type — skipped")
        return None

    return {
        "source_type": source_type,
        "scope": "3",
        "activity_date": parsed_row.get("expense_date"),
        "description": desc,
        "quantity": quantity,
        "unit": unit,
        "co2e_kg": co2e_kg,
        "emission_factor": Decimal(str(factor_info["factor"])) if factor_info else None,
        "emission_factor_source": factor_info["source"] if factor_info else "",
        "_errors": errors,
        "_raw": parsed_row.get("_raw", {}),
        "_distance_source": parsed_row.get("_distance_source"),
    }
