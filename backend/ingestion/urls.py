from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UploadView, BatchViewSet

router = DefaultRouter()
router.register("batches", BatchViewSet, basename="batch")

urlpatterns = [
    path("upload/", UploadView.as_view(), name="upload"),
    path("", include(router.urls)),
]
