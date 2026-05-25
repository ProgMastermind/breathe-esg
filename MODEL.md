# Data model

## Overview

The model is built around four concerns the assignment calls out explicitly:
multi-tenancy, Scope 1/2/3 categorisation, source-of-truth tracking, and audit trail.
Every design decision below is explained in terms of which concern it addresses.

---

## Entity relationship

```
Tenant
  └── User (AUTH_USER_MODEL)
  └── IngestionBatch
        └── RawRecord (one per CSV row)
              └── NormalizedRecord (one per parseable row)
                    └── ValidationFlag (zero or many per record)
  └── AuditLog (linked to NormalizedRecord)
```

---

## Tenant (core)

```python
Tenant:
  id         BigAutoField PK
  name       CharField(255)
  slug       SlugField unique
  created_at DateTimeField auto_now_add
```

Row-level multi-tenancy: every downstream model has a `tenant` FK and every query
filters by `request.user.tenant`. Simpler than schema-per-tenant without the operational
complexity of managing separate databases or dynamic schema switching per client.

The catch: a query that misses the tenant filter returns all tenants' data. The
production mitigation is a custom queryset manager that appends the filter automatically.
Not built in the prototype — see TRADEOFFS.md.

---

## User (core)

Extends Django's `AbstractUser` with a `tenant` FK. All DRF authentication
(token-based) goes through this model.

---

## IngestionBatch (ingestion)

```python
IngestionBatch:
  id           BigAutoField PK
  tenant       FK → Tenant
  source_type  CharField choices: sap_fuel | sap_procurement | utility_electricity |
                                   travel_flight | travel_hotel | travel_ground
  file_name    CharField(500)
  status       CharField choices: processing | completed | failed
  row_count    IntegerField default=0
  error_count  IntegerField default=0
  ingested_by  FK → User (nullable)
  ingested_at  DateTimeField auto_now_add
  notes        TextField blank
```

`source_type` lives on the batch rather than on individual records because a CSV file
from SAP is always one type — you don't mix fuel and procurement rows in the same upload
in practice. The analyst picks source type at upload time, so the normalizer always knows
what it's working with from context rather than guessing per row.

`file_name` instead of a `FileField` because we process the file at upload time and
discard it. Keeping the original file permanently would require object storage (S3/GCS)
and adds operational complexity. The file name is preserved for audit purposes only.

---

## RawRecord (ingestion)

```python
RawRecord:
  id          BigAutoField PK
  batch       FK → IngestionBatch CASCADE
  row_number  IntegerField
  raw_data    JSONField        -- original parsed row as key-value dict
  parse_error TextField null   -- populated if the row could not be parsed
  created_at  DateTimeField auto_now_add
```

This is the "source of truth" the assignment asks for. Every normalised record links
back to the exact contents of the original row. If an analyst questions where a CO2e
figure came from, `raw_data` shows them exactly what the source system sent.

`parse_error` allows rows to fail parsing without failing the whole batch. An analyst
can see "row 14 had a date format error" and go fix the source file.

JSONField rather than EAV: SAP exports have 30+ columns, utility exports ~10, travel
~15. A JSONField is far simpler to query and display than a generic attribute-value
table, and PostgreSQL's JSONB indexing handles specific key lookups efficiently if
needed later.

---

## NormalizedRecord (review)

```python
NormalizedRecord:
  id                     BigAutoField PK
  tenant                 FK → Tenant
  raw_record             OneToOneField → RawRecord (nullable)
  batch                  FK → IngestionBatch

  -- Classification
  source_type            CharField choices (same as IngestionBatch.source_type)
  scope                  CharField choices: 1 | 2 | 3

  -- Activity data (normalized)
  activity_date          DateField null
  description            CharField(500)
  quantity               DecimalField(20,6) null    -- in normalized unit
  unit                   CharField(50)              -- e.g. litres, kWh, passenger_km

  -- Emissions calculation
  co2e_kg                DecimalField(20,4) null
  emission_factor        DecimalField(20,8) null
  emission_factor_source CharField(200)

  -- Review workflow
  status                 CharField choices: pending | flagged | approved | rejected
  reviewed_by            FK → User null
  reviewed_at            DateTimeField null
  is_locked              BooleanField default=False
  analyst_notes          TextField blank

  -- Audit
  edit_history           JSONField default=list   -- append-only log of changes
  created_at             DateTimeField auto_now_add
```

Scope is assigned by the normalizer based on source type, not by the analyst:

| Source type           | Scope | Rationale |
|-----------------------|-------|-----------|
| sap_fuel              | 1     | Direct combustion of fuel by the company |
| sap_procurement       | 1     | Fuel/energy purchased for direct use |
| utility_electricity   | 2     | Purchased electricity (indirect) |
| travel_flight         | 3     | Business travel, not controlled by the company |
| travel_hotel          | 3     | Business travel accommodation |
| travel_ground         | 3     | Business travel ground transport |

Scope is not editable after ingestion. It's determined by source type, not by hand.
An analyst can reject a record and re-ingest with a correction, but scope doesn't have
a free-text override.

`quantity` and `unit` reflect the post-normalisation value. SAP sends litres, gallons,
cubic metres, kilograms — all converted to a canonical unit before storage. The raw
value is preserved in `RawRecord.raw_data`. This makes CO2e comparable across records
without unit gymnastics at query time:

| Raw unit          | Canonical unit | Conversion |
|-------------------|----------------|------------|
| L, Ltr, litre     | litres         | 1:1 |
| GAL               | litres         | ×3.78541 (US gallon) |
| KG (fuel)         | litres         | ÷ density (fuel-specific) |
| M3                | cubic_metres   | 1:1 |
| MWh (utility)     | kWh            | ×1000 |
| passenger_km      | passenger_km   | derived via haversine |
| room_nights       | room_nights    | 1:1 |

`co2e_kg` is nullable. For travel records where distance couldn't be derived (car
rentals, taxis without distance data), it's null rather than a silently wrong zero.
A `ValidationFlag` of type `travel_missing_distance` is created so the analyst can
see exactly why.

Records lock on approval (`is_locked = True`). The API returns 403 on any attempt to
modify a locked record.

`edit_history` is append-only: every status change or note update appends
`{changed_by, changed_at, changes: {field: {from, to}}}`. It's separate from AuditLog
and denormalised onto the record for efficient single-record display.

---

## ValidationFlag (review)

```python
ValidationFlag:
  id         BigAutoField PK
  record     FK → NormalizedRecord CASCADE
  flag_type  CharField choices: missing_required_field | future_date | negative_quantity |
                                 outlier_high | duplicate_record | utility_long_billing_period |
                                 travel_missing_distance | unit_conversion_assumption | zero_quantity
  message    TextField
  severity   CharField choices: error | warn | info
  resolved   BooleanField default=False
  created_at DateTimeField auto_now_add
```

Flags are a separate model rather than a JSONField so they're queryable: "give me all
records with an `outlier_high` flag that are still pending." A JSONField would make
that query expensive or impossible. A separate model also lets us add a "resolve flag"
workflow action later.

Severity: `error` means the calculation is likely wrong and sets the record status to
`flagged` automatically. `warn` means the data is suspicious but usable and the record
stays `pending`. `info` is a note about an assumption made (e.g. unit conversion) with
no status change.

---

## AuditLog (review)

```python
AuditLog:
  id           BigAutoField PK
  tenant       FK → Tenant
  record       FK → NormalizedRecord null (SET_NULL)
  action       CharField(100)
  changed_by   FK → User null
  changed_at   DateTimeField auto_now_add
  before_state JSONField default=dict
  after_state  JSONField default=dict
```

The AuditLog is the authoritative append-only ledger. It uses `SET_NULL` on the record
FK so it survives record deletion. For an auditor asking "was this record ever changed?",
AuditLog is the source of truth.

The difference from `edit_history` on `NormalizedRecord`: `edit_history` is denormalised
for fast single-record display. AuditLog covers events at the batch level and persists
beyond the record itself.

---

## What this model can't do

Three real gaps worth being clear about:

1. No emission factor versioning. DEFRA publishes new factors annually and the numbers
   change. A record from 2023 should use 2023 factors. Right now every record uses
   whatever factors were hardcoded at ingestion time. A proper implementation needs an
   `EmissionFactor` table with effective-date ranges and a recalculation mechanism.

2. No location-specific electricity factors. The model uses a single UK grid factor
   (0.2171 kgCO2e/kWh). A client with sites in the US, Germany, and India should use
   country-specific factors. The `emission_factor_source` field records what was used,
   but the pipeline doesn't accept a per-site country code.

3. No market-based Scope 2. The GHG Protocol allows two methods: location-based (what
   we do) and market-based (which accounts for renewable energy certificates). We only
   implement location-based.
