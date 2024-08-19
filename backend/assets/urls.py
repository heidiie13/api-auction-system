from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AssetViewSet, AppraiserViewSet, AssetMediaViewSet

router = DefaultRouter()
router.register(r"assets", AssetViewSet)
router.register(r"appraisers", AppraiserViewSet)
router.register(r"asset-media", AssetMediaViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
