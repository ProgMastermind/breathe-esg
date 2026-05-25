# Sources

For each of the three data sources: what real-world format I researched, what I
learned, what the sample data looks like and why, and what would break in a real
deployment.

---

## Source 1: SAP fuel and procurement

### What I researched

SAP's primary method of extracting goods movement data for sustainability teams is via
SE16N (General Table Display) on tables like MSEG (material document segment) or MB51
(material document list). Enterprise clients also sometimes use custom ABAP reports that
dump to CSV.

Key SAP field names I encountered:
- BUDAT / Buchungsdatum — posting date (DD.MM.YYYY in German locale)
- MATNR / Material — material number
- MAKTX / Materialbez — material description (often German: "Dieselkraftstoff")
- ERFMG / Menge — entered quantity
- ERFME / Mengeneinh — unit of measure (SAP internal codes: L, KG, M3, ST)
- KOSTL — cost centre
- WERKS / Werk — plant code
- MATKL / Materialgruppe — material group (numerically coded)
- NETWR / Betrag — net value
- WAERS / Waehr — currency

SAP unit-of-measure codes are non-standard. "L" means litres, but some older
configurations export "Ltr" as a non-standard alias. "M3" means cubic metres (common
for natural gas). "KG" means kilograms (some fuel is measured by mass).

### What I learned

The most important finding: SAP doesn't know what emission factors are. Material group
codes (e.g. "001") may mean "fuel" at one client and "office supplies" at another —
there's no universal mapping. A real implementation requires a client-specific material
group → fuel type mapping table. I hardcoded a reasonable default (001-009 → fuel/energy)
and fall back to keyword matching on the material description.

German decimal separators are a real problem: 1.234,56 (German format) versus 1,234.56
(English format). The parser handles both.

### Sample data

20 rows representing a German manufacturing plant (Buchungskreis 1000, plants PL01-PL04)
over Jan-May 2024:
- Diesel at PL01 (main transport depot) — realistic volumes: 3,000-6,000L/month
- Heating oil at PL02 — 2,000-3,000L/month
- Natural gas at PL03 — 760-1,100 M3/month
- Petrol at PL01 — 980-1,200L/month
- LPG at PL04 — 800-1,200L/month

Intentional quirks: row 7 has "Ltr" instead of "L" (a real typo seen in exports from
non-standard SAP configs); row 12 has zero quantity (cancelled delivery or data entry
error); row 17 has an unusually high diesel volume (18,500L) to trigger the outlier flag;
row 18 has heating oil in KG rather than L, requiring density conversion.

### What would break in a real deployment

1. Material group mapping: our hardcoded groups would need to be replaced with a
   client-specific lookup table. Client A's "001" is diesel; client B's "001" might be
   stationery.

2. Date formats: we handle 4 variants. SAP can produce others — YYYYMMDD without
   delimiters, and MM/DD/YYYY in some client configurations.

3. Plant code resolution: we store plant codes as-is. A real system needs a plant →
   country/site lookup to apply the correct emission factor, especially for electricity.

4. Character encoding: SAP exports can be UTF-8, UTF-16, Windows-1252, or ISO-8859-1
   depending on the system locale. We use `utf-8-sig` with `errors=replace` as a
   best-effort decode.

5. Multi-company exports: large enterprises export from multiple company codes with
   different currencies. We store the currency but don't convert.

---

## Source 2: Utility electricity

### What I researched

US and UK utility portals almost universally offer CSV download of billing history. The
format varies by utility, but the core fields are consistent: account number, meter
identifier, billing period start and end dates, usage in kWh, and total charge.

A few things stood out during research:

Billing periods don't align to calendar months. A "January" bill might cover Dec 30 to
Feb 1 (33 days). Meter reads happen when the meter reader visits, not on the 1st. This
causes headaches for monthly CO2e reporting.

Some large commercial meters report in MWh, not kWh. A data centre might show 12.8 MWh
where a small office shows 12,800 kWh. The column header is the only signal, so the
parser checks it explicitly.

UK meters use MPAN (Meter Point Administration Number) as the identifier rather than
a simple account number.

Green Button XML exists as a US standard but requires XML parsing and stores timestamps
as Unix epoch seconds with Watt-hours as integers. Most facilities teams just use the CSV
download button.

### What I learned

The hardest real-world problem is that a large enterprise has hundreds of meters across
dozens of sites, and the CSV download is per-account not per-building. Mapping meter IDs
to buildings and cost centres is a data quality problem that lives outside this app.

UK half-hourly settlement data (Elexon D0355 format) exists for sites with maximum demand
above 100 kW but is EDI-formatted and consumed by energy managers, not facilities teams.
Not relevant to the user persona here.

### Sample data

Three meters representing three real site types:
- MTR-001A — main office, SME, ~40,000-45,000 kWh/month, LV-SME-1 tariff
- MTR-002B — warehouse/industrial, high-voltage, reported in MWh (11.95-13.1 MWh/month)
  to test the MWh→kWh conversion
- MTR-003C — data centre rack suite, ~190,000-205,000 kWh/month

Intentional quirks: row 4 is missing its meter ID (tests the `missing_required_field`
flag); rows 5-8 report in MWh (tests unit detection); row 12 is a 34-day billing period
just under the 35-day warning threshold.

### What would break in a real deployment

1. Multi-utility clients: a client with sites in different countries will have completely
   different column names and date formats. Per-utility format profiles would be needed.

2. Tariff and demand charges: we capture Peak_Demand_kW but don't use it in emissions
   calculations.

3. Green tariffs and REGOs: if a client has purchased Renewable Energy Guarantees of
   Origin, their market-based Scope 2 would be zero. We have no way to capture this
   without knowing the energy contract.

4. Interval data: some clients may want half-hourly data to align emissions with grid
   carbon intensity, which varies significantly throughout the day. Monthly totals miss
   this granularity.

---

## Source 3: Corporate travel

### What I researched

SAP Concur is the dominant platform for enterprise corporate travel and expenses. The
standard CSV export gives expense-level data with fields including: employee name, report
ID, expense type, merchant/description, amount, currency, date, approval status, and
optional custom fields.

The most important thing here: the standard export does not include flight distance or
cabin class. These fields only appear if the Concur admin has explicitly added them as
custom fields in the configuration. Most companies have not done this — it's the default
state, not an edge case.

Navan (formerly TripActions) is the challenger platform gaining share among tech
companies. Navan provides more flight details in its exports (origin city, destination
city, carrier) because it's a booking platform as well as an expense tool. Concur is
primarily an expense tool; Navan handles booking too.

For the haversine calculation: I built a lookup table of ~120 major airports (IATA codes
→ lat/lon) and use the haversine formula for great-circle distance. This is accurate to
within 2-3% of actual flight path distance. DEFRA's methodology uses "great circle
distance + 9% upscale" for typical routing; I don't apply the upscale, which makes the
calculation slightly conservative.

DEFRA 2024 flight factors:
- Economy short-haul (<3,700km): 0.2551 kgCO2e/passenger-km
- Economy long-haul (>3,700km): 0.1951 kgCO2e/passenger-km
- Business short-haul: 0.4152 kgCO2e/passenger-km
- Business long-haul: 0.4290 kgCO2e/passenger-km

The 3,700km threshold is DEFRA's cutoff. LHR→JFK is ~5,540km (long-haul);
LHR→CDG is ~340km (short-haul).

### What I learned

Expense type categorisation is inconsistent. "Air Travel", "Airfare", "Flight",
"Aviation" all mean the same thing but appear differently depending on which employee
entered the expense. I built a keyword normalisation map to handle this.

Currency is almost always the billing currency, not GBP/USD base. A flight booked in
Singapore might show up in SGD. CO2e doesn't depend on currency — the amount field is
stored but not used in calculations.

Car rental expenses almost never include distance. The only way to calculate emissions
for car rental is duration and average daily mileage — neither of which Concur captures.
These records get flagged as missing distance.

### Sample data

25 rows covering Q1 2024 travel for 5 employees at a mid-sized UK-based company:
- Transatlantic (LHR-JFK, long-haul economy): the main cost centre
- European city pairs (LHR-TXL, LHR-BER, LHR-CDG, LHR-AMS): short-haul economy
- Long-haul Asia Pacific (LHR-SIN, LHR-BOM, LHR-SYD): some in business class
- Hotels: mixed 2-5 night stays
- Ground transport: Uber, rail, car rental

Intentional quirks: row 16 is a Paris trip with both a flight and a Eurostar for the
same journey (both get ingested as separate records); rows 22-24 are the Sydney trip
(LHR-SYD, ~17,000km round trip); row 25 is a local taxi with no airport codes (tests
the ground transport path); currencies include USD, EUR, GBP, SGD, and AUD.

### What would break in a real deployment

1. Missing airport codes for 40%+ of real Concur exports. Unless origin/destination
   custom fields have been configured, we parse them from free-text. This fails for
   domestic rail ("London Paddington to Birmingham New Street" has no IATA codes).

2. Multi-segment itineraries. A LHR→CDG→JFK booking might show as two expense lines.
   We'd calculate LHR→CDG and CDG→JFK separately, which is correct — but a single
   LHR→JFK direct booking would only get that one leg.

3. Navan API integration would be far superior to CSV export and would include
   segment-level flight data, hotel chain category, and spend analytics.

4. Hotel emission factors by country. We use the DEFRA UK factor for all hotels.
   A hotel in India has significantly different embodied energy per room-night than
   one in London.
