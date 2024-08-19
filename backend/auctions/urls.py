from rest_framework.routers import DefaultRouter
from .views import AuctionViewSet

router = DefaultRouter()
# router.register('auctions', AuctionViewSet)

urlpatterns = router.urls