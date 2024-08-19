from rest_framework import permissions
from .models import RegistrationFee, AssetDeposit, AuctionAsset
from .enums import PaymentStatus

class CanPlaceBid(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        auction_asset_id = request.data.get('auction_asset')
        if not auction_asset_id:
            return False
        user = request.user
        auction_asset = AuctionAsset.objects.get(id=auction_asset_id)
        return (
            RegistrationFee.objects.filter(user=user, auction=auction_asset.auction, registration_payment_status=PaymentStatus.PAID).exists() and
            AssetDeposit.objects.filter(user=user, auction_asset=auction_asset, deposit_payment_status=PaymentStatus.PAID).exists()
        )