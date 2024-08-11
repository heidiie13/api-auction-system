from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
# router.register('auctions', views.AuctionViewSet)
# router.register('auction-assets', views.AuctionAssetViewSet)
# router.register('asset-deposits', views.AssetDepositViewSet)
# router.register('bids', views.BidViewSet)
# router.register('fees', views.FeeViewSet)
# router.register('taxes', views.TaxViewSet)
# router.register('contracts', views.ContractViewSet)
# router.register('contract-fees', views.ContractFeeViewSet)
# router.register('contract-taxes', views.ContractTaxViewSet)
# router.register('transactions', views.TransactionHistoryViewSet)

urlpatterns = [
    path('', include(router.urls)),
]