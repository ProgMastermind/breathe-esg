# Decision log

Every ambiguity I resolved, what I chose, why, and what I'd ask the PM about.

---

## Source 1: SAP

### Which SAP export mechanism?

I went with SE16N flat file CSV rather than IDoc or OData. The overwhelming majority of
sustainability teams pulling data from SAP are not developers — they use the data browser
(SE16N transaction) or ask an SAP basis admin for a custom report. IDoc requires ABAP
development and a configured partner profile. OData requires a modern S/4HANA system with
the right authorisations. SE16N works on any SAP ERP version and produces a delimited file
with no development work involved.

The real-world pattern I was designing for: a sustainability manager gets an Excel export
emailed from the SAP team quarterly. That file has German column headers (SAP defaults
to German) and DD.MM.YYYY dates.

What the parser handles:
- Material goods movements (MSEG / MB51)
- Fuel and energy materials identified by material group (001-009, FUEL, ENRG) or by
  material description keyword matching in German and English
- Units: L, KG, M3, GAL, with a conversion layer for ambiguous codes ("Ltr" vs "L")
- Dates: DD.MM.YYYY with fallbacks for YYYY-MM-DD and MM/DD/YYYY

What it ignores:
- Goods receipts vs goods issues distinction (all movement quantities treated as positive consumption)
- Cost centre / plant hierarchy (codes captured but not resolved)
- Purchase orders vs material movements
- Non-fuel procurement (items not matching fuel material groups return None from the normalizer and are skipped)

What I'd ask the PM:
- Do clients run SAP ECC 6.0 or S/4HANA? (Affects whether OData is feasible)
- Is this a regular export or a one-time migration? (Frequency determines whether to build a pull mechanism)
- Which material groups are in scope for Scope 1? (Hardcoded to 001-009 now)
- Is plant code meaningful for emission factor selection (e.g. different countries)?

---

## Source 2: Utility electricity

### Which format?

Portal CSV export, not Green Button XML or UK half-hourly EDI. Facilities managers are
the people downloading this data, and every UK utility portal gives them a CSV button.
Green Button XML is the US standard but requires XML parsing, and the schema has changed
between versions. UK half-hourly EDI (D0355) is used by Elexon participants — not the
facilities team persona who would use this app.

Green Button is worth supporting in a v2 but adds implementation complexity (XML
namespaces, Unix epoch timestamps, Watt-hours as integers) that isn't justified for
a prototype.

What the parser handles:
- Monthly or billing-period CSV with usage in kWh or MWh
- MWh vs kWh detection by column header (large commercial sites may export in MWh)
- Billing periods up to 35 days (metered in 28-35 day cycles, not calendar months)
- Account number, meter ID, service address preserved from source
- UK grid emission factor (DEFRA 2024: 0.2171 kgCO2e/kWh)

What it ignores:
- Multi-tariff structures (E7/off-peak, time-of-use) — only total kWh captured
- Power factor / reactive power
- Gas and water from the same utility bill
- Market-based Scope 2 (REGOs, green tariffs) — see MODEL.md

Validation: billing periods over 35 days flag as a likely combined bill or meter read
skip. MWh-to-kWh conversion logs a `unit_conversion_assumption` flag.

What I'd ask the PM:
- Are all client sites in the UK, or do we need country-specific emission factors?
- Do any clients have on-site solar/wind that should be subtracted from consumption?
- Is interval-level (half-hourly) data ever needed, or is billing-period total sufficient?

---

## Source 3: Corporate travel

### Which platform and format?

SAP Concur CSV export. Concur is the dominant corporate travel platform in enterprise
accounts that also use SAP ERP — and the assignment says the client has fuel and
procurement data in SAP. A company using SAP for finance almost always uses Concur for
travel. The CSV export is what sustainability teams get when they don't have API access.

The most important thing I learned researching this format: standard Concur exports don't
include flight distance or cabin class. These fields only appear if the Concur admin has
added them as custom fields in the configuration. Most companies haven't done this —
it's the default state, not an edge case.

My response: derive distance from IATA airport codes using haversine, with a built-in
lookup table of ~120 major airports. The parser also tries to extract airport codes from
free-text merchant/memo fields via regex when explicit departure/arrival columns are blank.
For records where distance still can't be derived (car rentals, taxis, rail), `co2e_kg`
is null rather than silently wrong, and a `travel_missing_distance` flag is raised.

What the parser handles:
- Flights: IATA origin/destination → haversine distance → DEFRA factor by haul length
- Hotels: room nights × DEFRA hotel factor
- Car rental: flagged as missing distance (no CO2e without km data)
- Taxi/rideshare: flagged as missing distance
- Rail: flagged as missing distance

What it ignores:
- Connecting flights (each segment treated as a separate row)
- Cabin class premium for first class (treated as business class)
- Radiative forcing index multiplier for aviation — controversial and not in DEFRA standard methodology
- Currency conversion (original currency stored; amount field is reference only, not used in CO2e)

What I'd ask the PM:
- Are clients using Concur, Navan, or something else? Navan's API integration would be significantly better than CSV export.
- Should we include commuting travel (Scope 3 Category 7) or just business travel?
- Do clients want a radiative forcing multiplier for flights? DEFRA doesn't mandate it but some clients ask for it.
- Are international hotel stays in scope? Using UK DEFRA factor for all hotels right now.

---

## Authentication

DRF token authentication, stored in localStorage. For a prototype with one analyst
persona this is fine. Production would need HttpOnly cookies and proper CSRF handling,
OAuth2/OIDC for corporate SSO, and role-based access control separating read-only
auditors from analysts who can approve records.

---

## Synchronous ingestion

No Celery. The upload endpoint runs the full parse → normalise → validate → persist
pipeline synchronously before returning a 201.

Celery requires a broker (Redis or RabbitMQ), a worker process, a results backend, and
monitoring for failed tasks — three additional infrastructure components for a prototype
handling files of 12-100 rows. At those volumes the pipeline completes in under 200ms
and the analyst gets immediate feedback. The cost at enterprise scale is in TRADEOFFS.md.

---

## Multi-tenancy

Row-level tenant FK on every model. Every view filters by `request.user.tenant`. Simpler
than schema-per-tenant (no dynamic schema switching, no per-tenant migrations) and
perfectly adequate for 2-10 tenants.

The risk is a view that omits the filter leaking cross-tenant data. Production mitigation
is a custom queryset manager. Not built in the prototype — TRADEOFFS.md covers this.

---

## Emission factors

DEFRA 2024 GHG Conversion Factors throughout. They cover all three source types, they're
free and publicly available, and they're the standard for UK GHG reporting. The main gap
is factor versioning: a record from 2023 should use 2023 factors, not 2024. DEFRA updates
annually (typically June), and there's no way to retroactively recalculate old records
against a new version without re-ingesting. TRADEOFFS.md has the full discussion.

---

## Deployment

Railway, for managed PostgreSQL as an addon, auto-deploy from GitHub, and a free tier
sufficient for a prototype. `DATABASE_URL` is set automatically; `dj-database-url` parses
it. No Dockerfile required.

Frontend is built to `backend/static/dist/` and served by WhiteNoise as static files.
Single-process, single-dyno deployment.
