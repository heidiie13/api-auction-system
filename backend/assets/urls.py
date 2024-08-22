from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AssetReadOnlyViewSet, AssetViewSet, AppraiserViewSet, AssetMediaViewSet

router = DefaultRouter()
router.register("assets", AssetViewSet, basename="assets")
router.register("appraisers", AppraiserViewSet, basename="appraisers")
router.register("asset-media", AssetMediaViewSet, basename="asset-media")
router.register("assets/read-only", AssetReadOnlyViewSet, basename="assets-read")

urlpatterns = [
    path("", include(router.urls)),
]
