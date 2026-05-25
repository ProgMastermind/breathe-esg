from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NormalizedRecordViewSet, DashboardView

router = DefaultRouter()
router.register("records", NormalizedRecordViewSet, basename="record")

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("", include(router.urls)),
]
