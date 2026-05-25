from decimal import Decimal
from ingestion.emission_factors import FACTORS, SAP_FUEL_MAP, SAP_UOM_MAP, to_litres


FUEL_MATERIAL_GROUPS = {"001", "002", "003", "004", "005", "B001", "B002", "FUEL", "ENRG", "0001"}


def _identify_fuel_type(description: str, material_group: str) -> str | None:
    desc_lower = description.lower().strip()
    for keyword, fuel_key in SAP_FUEL_MAP.items():
        if keyword in desc_lower:
            return fuel_key
    # Fall back to material group
    if str(material_group).upper() in FUEL_MATERIAL_GROUPS:
        return "diesel"  # safest default for fuel group
    return None


def normalize(parsed_row: dict) -> dict | None:
    """
    Returns a dict ready to populate NormalizedRecord, or None if the row
    cannot be normalized (e.g. non-fuel procurement item with no emission factor).
    """
    errors = parsed_row.get("_parse_errors", [])

    quantity = parsed_row.get("quantity")
    uom_raw = parsed_row.get("unit", "")
    unit = SAP_UOM_MAP.get(uom_raw, SAP_UOM_MAP.get(uom_raw.strip(), None))
    description = parsed_row.get("material_description", "")
    material_group = parsed_row.get("material_group", "")

    fuel_type = _identify_fuel_type(description, material_group)
    if not fuel_type:
        # Not a fuel/energy material — skip (procurement without emission factor)
        return None

    factor_info = FACTORS.get(fuel_type)
    if not factor_info:
        return None

    co2e_kg = None
    norm_quantity = quantity
    norm_unit = unit or uom_raw

    if quantity is not None and unit:
        if unit in ("litres", "gallons", "cubic_metres"):
            litres = to_litres(float(quantity), unit)
            if litres is not None:
                if fuel_type == "natural_gas":
                    # natural gas factor is per m³ not per litre
                    m3 = litres / 1000
                    co2e_kg = Decimal(str(m3 * factor_info["factor"]))
                    norm_quantity = Decimal(str(m3))
                    norm_unit = "cubic_metres"
                else:
                    co2e_kg = Decimal(str(litres * factor_info["factor"]))
                    norm_quantity = Decimal(str(litres))
                    norm_unit = "litres"
        elif unit == "kg":
            # Diesel density ≈ 0.845 kg/L; petrol ≈ 0.755 kg/L; fuel oil ≈ 0.87 kg/L
            density_map = {"diesel": 0.845, "petrol": 0.755, "fuel_oil": 0.870, "lpg": 0.542}
            density = density_map.get(fuel_type, 0.845)
            litres = float(quantity) / density
            co2e_kg = Decimal(str(litres * factor_info["factor"]))
            norm_quantity = Decimal(str(litres))
            norm_unit = "litres"
            errors = errors + ["Unit converted from kg to litres using density assumption"]

    has_unit_assumption = unit != uom_raw or uom_raw not in SAP_UOM_MAP

    return {
        "source_type": "sap_fuel",
        "scope": "1",
        "activity_date": parsed_row.get("posting_date"),
        "description": f"{description} [{parsed_row.get('material_number', '')}] @ {parsed_row.get('plant', '')}",
        "quantity": norm_quantity,
        "unit": norm_unit,
        "co2e_kg": co2e_kg,
        "emission_factor": Decimal(str(factor_info["factor"])) if factor_info else None,
        "emission_factor_source": factor_info["source"] if factor_info else "",
        "_errors": errors,
        "_unit_assumption": has_unit_assumption,
        "_raw": parsed_row.get("_raw", {}),
        "_fuel_type": fuel_type,
    }
