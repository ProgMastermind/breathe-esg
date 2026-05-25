from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.parsers import MultiPartParser, FormParser

from .models import IngestionBatch, SourceType
from .serializers import IngestionBatchSerializer
from .pipeline import run


VALID_SOURCE_TYPES = {c[0] for c in SourceType.choices}


class UploadView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file_obj = request.FILES.get("file")
        source_type = request.data.get("source_type", "").strip()

        if not file_obj:
            return Response({"error": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)
        if source_type not in VALID_SOURCE_TYPES:
            return Response(
                {"error": f"Invalid source_type. Must be one of: {', '.join(VALID_SOURCE_TYPES)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tenant = request.user.tenant
        if not tenant:
            return Response({"error": "User has no tenant assigned."}, status=status.HTTP_403_FORBIDDEN)

        batch = IngestionBatch.objects.create(
            tenant=tenant,
            source_type=source_type,
            file_name=file_obj.name,
            ingested_by=request.user,
        )

        content = file_obj.read()
        run(batch, content)
        batch.refresh_from_db()

        return Response(IngestionBatchSerializer(batch).data, status=status.HTTP_201_CREATED)


class BatchViewSet(ReadOnlyModelViewSet):
    serializer_class = IngestionBatchSerializer

    def get_queryset(self):
        qs = IngestionBatch.objects.filter(tenant=self.request.user.tenant)
        source_type = self.request.query_params.get("source_type")
        if source_type:
            qs = qs.filter(source_type=source_type)
        return qs
