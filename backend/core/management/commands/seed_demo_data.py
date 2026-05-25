"""
Creates demo tenant, user, and ingests all three sample CSV files.
Run: python manage.py seed_demo_data
"""

import os
from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import Tenant, User
from ingestion.models import IngestionBatch
from ingestion.pipeline import run


SAMPLE_DIR = os.path.join(settings.BASE_DIR.parent, "sample_data")


class Command(BaseCommand):
    help = "Seed demo tenant, user, and sample ingestion data"

    def handle(self, *args, **options):
        tenant, _ = Tenant.objects.get_or_create(name="Acme Corp", defaults={"slug": "acme-corp"})
        self.stdout.write(f"Tenant: {tenant}")

        if not User.objects.filter(username="analyst").exists():
            user = User.objects.create_user(
                username="analyst",
                email="analyst@demo.com",
                password="breathe2024",
                first_name="Alex",
                last_name="Analyst",
                tenant=tenant,
            )
            self.stdout.write(f"User created: {user.username} / breathe2024")
        else:
            user = User.objects.get(username="analyst")
            user.tenant = tenant
            user.save()
            self.stdout.write(f"User exists: {user.username}")

        samples = [
            ("sap_fuel_sample.csv", "sap_fuel"),
            ("utility_electricity_sample.csv", "utility_electricity"),
            ("travel_sample.csv", "travel_flight"),
        ]

        for filename, source_type in samples:
            if IngestionBatch.objects.filter(tenant=tenant, file_name=filename).exists():
                self.stdout.write(f"Batch already exists for {filename}, skipping.")
                continue

            path = os.path.join(SAMPLE_DIR, filename)
            if not os.path.exists(path):
                self.stdout.write(self.style.WARNING(f"Sample file not found: {path}"))
                continue

            with open(path, "rb") as f:
                content = f.read()

            batch = IngestionBatch.objects.create(
                tenant=tenant,
                source_type=source_type,
                file_name=filename,
                ingested_by=user,
            )
            run(batch, content)
            batch.refresh_from_db()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Ingested {filename}: {batch.row_count} rows, {batch.error_count} errors, status={batch.status}"
                )
            )

        self.stdout.write(self.style.SUCCESS("\nDemo data seeded successfully."))
        self.stdout.write("Login: username=analyst, password=breathe2024")
