from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.core.exceptions import ValidationError
from .models import Auction, AuctionAsset, AssetDeposit, Bid, Fee, Tax, Contract, ContractFee, ContractTax, TransactionHistory
from .serializers import AuctionSerializer, AuctionAssetSerializer, AssetDepositSerializer, BidSerializer, FeeSerializer, TaxSerializer, ContractSerializer, ContractFeeSerializer, ContractTaxSerializer, TransactionHistorySerializer
from users.permissions import IsAdminUser, IsStaffUser
from assets.models import Asset, AssetStatus, AssetAppraisalStatus

class AuctionViewSet(viewsets.ModelViewSet):
    queryset = Auction.objects.all()
    serializer_class = AuctionSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsStaffUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        auction = self.get_object()
        auction.update_status()
        return Response({'status': 'Auction status updated'})

    @action(detail=False, methods=['post'])
    def create_auction_with_assets(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        auction = serializer.save()

        available_assets = Asset.objects.filter(
            status=AssetStatus.PENDING,
            appraise_status=AssetAppraisalStatus.APPRAISAL_SUCCESSFUL
        ).order_by('created_date')[:auction.max_assets]

        for asset in available_assets:
            AuctionAsset.objects.create(auction=auction, asset=asset)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

class AuctionAssetViewSet(viewsets.ModelViewSet):
    queryset = AuctionAsset.objects.all()
    serializer_class = AuctionAssetSerializer
    permission_classes = [IsStaffUser]

    @action(detail=False, methods=['post'])
    def add_asset_to_auction(self, request):
        asset_id = request.data.get('asset_id')
        auction_id = request.data.get('auction_id')

        try:
            asset = Asset.objects.get(id=asset_id, status=AssetStatus.PENDING, appraise_status=AssetAppraisalStatus.APPRAISAL_SUCCESSFUL)
            auction = Auction.objects.get(id=auction_id)
        except (Asset.DoesNotExist, Auction.DoesNotExist):
            return Response({'error': 'Invalid asset or auction'}, status=status.HTTP_400_BAD_REQUEST)

        if auction.assets.count() >= auction.max_assets:
            return Response({'error': 'Auction has reached maximum number of assets'}, status=status.HTTP_400_BAD_REQUEST)

        auction_asset = AuctionAsset.objects.create(auction=auction, asset=asset)
        serializer = self.get_serializer(auction_asset)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class AssetDepositViewSet(viewsets.ModelViewSet):
    queryset = AssetDeposit.objects.all()
    serializer_class = AssetDepositSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.IsAuthenticated]
        elif self.action in ['create']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [IsStaffUser]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class BidViewSet(viewsets.ModelViewSet):
    queryset = Bid.objects.all()
    serializer_class = BidSerializer

    def get_permissions(self):
        if self.action in ['create']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [IsStaffUser]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        user = self.request.user
        auction_asset = serializer.validated_data['auction_asset']
        
        # Check if user has an approved deposit for this auction asset
        if not AssetDeposit.objects.filter(user=user, auction_asset=auction_asset, is_approved=True).exists():
            raise ValidationError("You must have an approved deposit to bid on this asset.")

        # Check if the bid amount is higher than the current price
        if serializer.validated_data['amount'] <= auction_asset.current_price:
            raise ValidationError("Bid amount must be higher than the current price.")

        serializer.save(user=user)
        
        # Update the auction asset's current price and bid count
        auction_asset.current_price = serializer.validated_data['amount']
        auction_asset.bid_count += 1
        auction_asset.save()

class FeeViewSet(viewsets.ModelViewSet):
    queryset = Fee.objects.all()
    serializer_class = FeeSerializer
    permission_classes = [IsAdminUser]

class TaxViewSet(viewsets.ModelViewSet):
    queryset = Tax.objects.all()
    serializer_class = TaxSerializer
    permission_classes = [IsAdminUser]

class ContractViewSet(viewsets.ModelViewSet):
    queryset = Contract.objects.all()
    serializer_class = ContractSerializer
    permission_classes = [IsStaffUser]

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        contract = self.get_object()
        contract.update_status()
        return Response({'status': 'Contract status updated'})

class ContractFeeViewSet(viewsets.ModelViewSet):
    queryset = ContractFee.objects.all()
    serializer_class = ContractFeeSerializer
    permission_classes = [IsStaffUser]

    @action(detail=True, methods=['post'])
    def update_amount(self, request, pk=None):
        contract_fee = self.get_object()
        contract_fee.update_amount()
        return Response({'status': 'Contract fee amount updated'})

class ContractTaxViewSet(viewsets.ModelViewSet):
    queryset = ContractTax.objects.all()
    serializer_class = ContractTaxSerializer
    permission_classes = [IsStaffUser]

    @action(detail=True, methods=['post'])
    def update_amount(self, request, pk=None):
        contract_tax = self.get_object()
        contract_tax.update_amount()
        return Response({'status': 'Contract tax amount updated'})

class TransactionHistoryViewSet(viewsets.ModelViewSet):
    queryset = TransactionHistory.objects.all()
    serializer_class = TransactionHistorySerializer
    permission_classes = [IsStaffUser]

    def get_queryset(self):
        if self.request.user.is_staff:
            return TransactionHistory.objects.all()
        return TransactionHistory.objects.filter(user=self.request.user)