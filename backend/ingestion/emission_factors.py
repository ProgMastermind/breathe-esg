# DEFRA 2024 GHG Conversion Factors (kgCO2e per unit)
# Source: UK Government GHG Conversion Factors for Company Reporting 2024
# https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2024

FACTORS = {
    # Scope 1  -  fuels (per litre unless noted)
    "diesel": {"factor": 2.6765, "unit": "litres", "source": "DEFRA 2024 - Diesel"},
    "petrol": {"factor": 2.3092, "unit": "litres", "source": "DEFRA 2024 - Petrol"},
    "natural_gas": {"factor": 2.0426, "unit": "cubic_metres", "source": "DEFRA 2024 - Natural Gas"},
    "lpg": {"factor": 1.5491, "unit": "litres", "source": "DEFRA 2024 - LPG"},
    "fuel_oil": {"factor": 3.1530, "unit": "litres", "source": "DEFRA 2024 - Fuel Oil"},

    # Scope 2  -  electricity (per kWh)
    "electricity_uk": {"factor": 0.2171, "unit": "kWh", "source": "DEFRA 2024 - UK Grid Electricity"},
    "electricity_us": {"factor": 0.3860, "unit": "kWh", "source": "EPA 2024 - US Grid Electricity"},
    "electricity_eu": {"factor": 0.2550, "unit": "kWh", "source": "EEA 2024 - EU Grid Electricity"},

    # Scope 3  -  travel
    "flight_short_haul_economy": {"factor": 0.2551, "unit": "passenger_km", "source": "DEFRA 2024 - Short Haul Economy (<3700km)"},
    "flight_long_haul_economy": {"factor": 0.1951, "unit": "passenger_km", "source": "DEFRA 2024 - Long Haul Economy (>3700km)"},
    "flight_short_haul_business": {"factor": 0.4152, "unit": "passenger_km", "source": "DEFRA 2024 - Short Haul Business"},
    "flight_long_haul_business": {"factor": 0.4290, "unit": "passenger_km", "source": "DEFRA 2024 - Long Haul Business"},
    "hotel_uk": {"factor": 0.0713, "unit": "room_nights", "source": "DEFRA 2024 - Hotel Stay UK"},
    "hotel_global": {"factor": 0.0897, "unit": "room_nights", "source": "DEFRA 2024 - Hotel Stay Global"},
    "car_rental_average": {"factor": 0.1921, "unit": "km", "source": "DEFRA 2024 - Car (Average)"},
    "taxi": {"factor": 0.1491, "unit": "km", "source": "DEFRA 2024 - Taxi"},
    "rail": {"factor": 0.0410, "unit": "km", "source": "DEFRA 2024 - National Rail"},
}

# Maps SAP material descriptions to fuel type keys
SAP_FUEL_MAP = {
    "diesel": "diesel",
    "dieselkraftstoff": "diesel",
    "heizoel": "fuel_oil",
    "heizöl": "fuel_oil",
    "benzin": "petrol",
    "petrol": "petrol",
    "erdgas": "natural_gas",
    "natural gas": "natural_gas",
    "lpg": "lpg",
    "flüssiggas": "lpg",
}

# Maps SAP unit codes to our standard units
SAP_UOM_MAP = {
    "L": "litres",
    "LTR": "litres",
    "Ltr": "litres",  # typo variant seen in real exports
    "l": "litres",
    "KG": "kg",
    "kg": "kg",
    "M3": "cubic_metres",
    "m3": "cubic_metres",
    "M³": "cubic_metres",
    "GAL": "gallons",
    "gal": "gallons",
    "ST": "pieces",   # Stück  -  often procured items, not fuel
    "EA": "pieces",   # Each
    "PAL": "pallets",
    "TO": "tonnes",
    "T": "tonnes",
}

LITRE_CONVERSIONS = {
    "gallons": 3.78541,  # US gallons to litres
    "litres": 1.0,
    "cubic_metres": 1000.0,
}


def to_litres(quantity: float, unit: str) -> float | None:
    factor = LITRE_CONVERSIONS.get(unit)
    if factor is None:
        return None
    return quantity * factor


def get_fuel_factor(fuel_type: str) -> dict | None:
    return FACTORS.get(fuel_type)
