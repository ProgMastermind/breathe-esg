# Tradeoffs

Three things I deliberately did not build, and why.

---

## 1. Async ingestion

The pipeline runs synchronously in the HTTP request. The upload endpoint runs the full
parse → normalise → validate → persist pipeline before returning a 201.

Celery was the obvious alternative — a broker (Redis or RabbitMQ), a worker process,
a results backend, and monitoring for failed tasks. That's three additional infrastructure
components for a prototype handling files of 12-100 rows. At those volumes the pipeline
completes in under 200ms. The analyst sees the batch row count and error count immediately
after upload, which is actually better UX than a polling spinner for files this small.

At enterprise scale (a client's annual SAP fuel export could be 50,000 rows), the HTTP
request would hold a connection for several seconds and risk a load-balancer timeout. The
right fix is to return a `202 Accepted` with a batch ID immediately, process in the
background, and let the frontend poll or use WebSockets for progress. The model is already
set up for this: `IngestionBatch.status = "processing"` is set at creation and flips to
"completed" or "failed" when the pipeline finishes. Adding async means wiring
`pipeline.run()` into a Celery task — the rest of the codebase doesn't change.

---

## 2. Emission factor versioning

The factors are a Python dictionary in `emission_factors.py` — DEFRA 2024 values,
hardcoded. Every NormalizedRecord stores the factor value and source string at
calculation time.

The proper version of this is an `EmissionFactor` database table with effective-date
ranges and source-version tracking. DEFRA publishes new factors annually, typically in
June. The 2023-to-2024 difference is around 1-8% depending on the fuel type — small
enough that for a prototype evaluating architecture, it's an acceptable gap.

The real problem shows up at scale: a record ingested in January 2024 and one ingested
in January 2025 will have used different factor values (because the Python file got
updated between them), but there's no mechanism to retroactively recalculate old records
against a new factor version without re-ingesting from the source file. A production
system needs a `FactorVersion` table, records linked to a specific version FK, and a
"recalculate with latest factors" job. The `emission_factor` and `emission_factor_source`
fields on NormalizedRecord are already in place for when that gets built.

---

## 3. Tenant isolation enforcement

Every view has an explicit `.filter(tenant=request.user.tenant)`. That handles the views
that exist today. The risk is a developer adding a new view and forgetting the filter —
which silently returns data for all tenants to whoever is authenticated. No exception, no
error, just wrong data.

The production fix is a custom `TenantManager` that overrides `get_queryset()` to
automatically filter by the current tenant:

```python
class TenantManager(models.Manager):
    def get_queryset(self):
        from threading import local
        _thread_locals = local()
        tenant = getattr(_thread_locals, 'tenant', None)
        if tenant:
            return super().get_queryset().filter(tenant=tenant)
        return super().get_queryset()
```

Or, simpler, use `django-tenant-schemas` or `django-tenants`, which handle this at the
database level. For a prototype with one developer writing all the views, explicit filters
work fine. For a team, it's a liability.
