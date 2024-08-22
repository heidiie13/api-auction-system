from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AuctionAssetReadViewSet, AuctionAssetViewSet, AuctionViewSet, BidViewSet, ContractViewSet, RegistrationFeeViewSet, AssetDepositViewSet,
    TaxViewSet, FeeViewSet, ContractTaxViewSet, ContractFeeViewSet
)

router = DefaultRouter()
router.register('auctions', AuctionViewSet, basename='auction')
router.register(r'auctions/(?P<auction_pk>\d+)/assets', AuctionAssetReadViewSet, basename='read-auction-assets')
# router.register('auction-assets', AuctionAssetViewSet, basename='auction-assets')
router.register('bids', BidViewSet, basename='bid')
router.register('contracts', ContractViewSet, basename='contract')
router.register('taxes', TaxViewSet, basename='tax')
router.register('fees', FeeViewSet, basename='fee')
router.register('contract-taxes', ContractTaxViewSet, basename='contract-tax')
router.register('contract-fees', ContractFeeViewSet, basename='contract-fee')
router.register('registrations', RegistrationFeeViewSet, basename='registration')
router.register('deposits', AssetDepositViewSet, basename='deposit')

urlpatterns = [
    path('', include(router.urls)),
]
