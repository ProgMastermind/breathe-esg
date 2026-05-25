from django.db.models import Sum, Count, Q
from django.utils import timezone
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import NormalizedRecord, AuditLog, ValidationFlag
from .serializers import NormalizedRecordSerializer, AuditLogSerializer
import django_filters


class NormalizedRecordFilter(django_filters.FilterSet):
    batch = django_filters.NumberFilter(field_name="batch__id")
    has_flags = django_filters.BooleanFilter(method="filter_has_flags")
    scope = django_filters.CharFilter(field_name="scope")
    status = django_filters.CharFilter(field_name="status")
    source_type = django_filters.CharFilter(field_name="source_type")

    class Meta:
        model = NormalizedRecord
        fields = ["batch", "scope", "status", "source_type"]

    def filter_has_flags(self, queryset, name, value):
        if value:
            return queryset.filter(flags__isnull=False).distinct()
        return queryset.filter(flags__isnull=True)


class NormalizedRecordViewSet(viewsets.ModelViewSet):
    serializer_class = NormalizedRecordSerializer
    filterset_class = NormalizedRecordFilter
    ordering_fields = ["activity_date", "co2e_kg", "created_at", "status"]
    ordering = ["-activity_date"]
    http_method_names = ["get", "patch", "post", "head", "options"]

    def get_queryset(self):
        return NormalizedRecord.objects.filter(
            tenant=self.request.user.tenant
        ).select_related("raw_record", "reviewed_by").prefetch_related("flags")

    def partial_update(self, request, *args, **kwargs):
        record = self.get_object()
        if record.is_locked:
            return Response(
                {"error": "Record is locked after approval and cannot be modified."},
                status=status.HTTP_403_FORBIDDEN,
            )

        before = {"status": record.status, "analyst_notes": record.analyst_notes}

        allowed_fields = {"status", "analyst_notes"}
        data = {k: v for k, v in request.data.items() if k in allowed_fields}

        new_status = data.get("status")
        if new_status == "approved":
            record.approve(request.user)
            data.pop("status", None)
        elif new_status == "rejected":
            record.reject(request.user, notes=data.pop("analyst_notes", ""))
        
        for field, value in data.items():
            setattr(record, field, value)
        record.save()

        after = {"status": record.status, "analyst_notes": record.analyst_notes}
        AuditLog.objects.create(
            tenant=request.user.tenant,
            record=record,
            action=f"Updated record #{record.pk}",
            changed_by=request.user,
            before_state=before,
            after_state=after,
        )
        record.edit_history.append({
            "changed_by": request.user.username,
            "changed_at": timezone.now().isoformat(),
            "changes": {k: {"from": before.get(k), "to": after.get(k)} for k in before if before[k] != after.get(k)}
        })
        record.save(update_fields=["edit_history"])

        return Response(NormalizedRecordSerializer(record).data)

    @action(detail=False, methods=["post"], url_path="bulk-action")
    def bulk_action(self, request):
        ids = request.data.get("ids", [])
        action_type = request.data.get("action", "")
        notes = request.data.get("notes", "")

        if action_type not in ("approve", "reject"):
            return Response({"error": "action must be 'approve' or 'reject'"}, status=400)

        records = NormalizedRecord.objects.filter(
            tenant=request.user.tenant, pk__in=ids, is_locked=False
        )
        updated = 0
        audit_logs = []
        for record in records:
            before = {"status": record.status}
            if action_type == "approve":
                record.approve(request.user)
            else:
                record.reject(request.user, notes=notes)
            after = {"status": record.status}
            audit_logs.append(AuditLog(
                tenant=request.user.tenant,
                record=record,
                action=f"Bulk {action_type}",
                changed_by=request.user,
                before_state=before,
                after_state=after,
            ))
            updated += 1

        AuditLog.objects.bulk_create(audit_logs)
        return Response({"updated": updated})

    @action(detail=True, methods=["get"])
    def audit_log(self, request, pk=None):
        record = self.get_object()
        logs = AuditLog.objects.filter(record=record)
        return Response(AuditLogSerializer(logs, many=True).data)


class DashboardView(APIView):
    def get(self, request):
        tenant = request.user.tenant
        qs = NormalizedRecord.objects.filter(tenant=tenant)

        total = qs.count()
        by_status = {
            "pending": qs.filter(status="pending").count(),
            "flagged": qs.filter(status="flagged").count(),
            "approved": qs.filter(status="approved").count(),
            "rejected": qs.filter(status="rejected").count(),
        }

        by_scope = {}
        for scope_val in ("1", "2", "3"):
            scope_qs = qs.filter(scope=scope_val)
            by_scope[scope_val] = {
                "count": scope_qs.count(),
                "co2e_kg": float(scope_qs.aggregate(t=Sum("co2e_kg"))["t"] or 0),
            }

        by_source = []
        from ingestion.models import SourceType
        for src_val, src_label in SourceType.choices:
            src_qs = qs.filter(source_type=src_val)
            cnt = src_qs.count()
            if cnt:
                by_source.append({
                    "source_type": src_val,
                    "label": src_label,
                    "count": cnt,
                    "co2e_kg": float(src_qs.aggregate(t=Sum("co2e_kg"))["t"] or 0),
                })

        return Response({
            "total": total,
            "by_status": by_status,
            "by_scope": by_scope,
            "by_source": by_source,
        })
