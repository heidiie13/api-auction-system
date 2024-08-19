from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Q
from .models import Auction, AuctionAsset, RegistrationFee, AssetDeposit, Bid, Contract, Tax, Fee, ContractTax, ContractFee
from .serializers import (
    AuctionSerializer, RegistrationFeeSerializer,
    AssetDepositSerializer, BidSerializer, ContractSerializer, TaxSerializer, FeeSerializer, ContractFeeSerializer, ContractTaxSerializer
)
from .enums import AuctionStatus, PaymentStatus, ContractStatus
from .permissions import CanPlaceBid
from assets.enums import AssetStatus
from assets.models import Asset, AssetAppraisalStatus
from users.permissions import IsAdminUser, IsStaffUser
from random import sample
from auctions import constants


class AuctionViewSet(viewsets.ModelViewSet):
    queryset = Auction.objects.all()
    serializer_class = AuctionSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdminUser | IsStaffUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        time_period = self.request.data.get('time_period')
        registration_start_date = self.request.data.get('registration_start_date')
        category = self.request.data.get('category')

        eligible_assets = Asset.objects.filter(
            Q(category=category) &
            Q(appraise_status=AssetAppraisalStatus.APPRAISAL_SUCCESSFUL) &
            Q(status=AssetStatus.PENDING)
        )
        
        asset_count = min(eligible_assets.count(), 3)
        if asset_count < 1:
            auction.delete()
            raise ValidationError("Not enough eligible assets to create an auction.")
                
        registration_start_at, registration_end_at, start_at, end_at = self.calculate_auction_dates(
            registration_start_date, time_period, asset_count
        )
        
        if self.is_auction_slot_available(start_at, end_at):
            auction = serializer.save(
                registration_start_at=registration_start_at,
                registration_end_at=registration_end_at,
                start_at=start_at,
                end_at=end_at,
                status=AuctionStatus.REGISTRATION
            )
            self.add_random_assets(auction, eligible_assets, asset_count)
        else:
            raise ValidationError("There is already an auction scheduled for this time period.")


    def is_auction_slot_available(self, start_at, end_at):
        overlapping_auctions = Auction.objects.filter(
            Q(start_at__lt=end_at) & Q(end_at__gt=start_at)
        )
        return not overlapping_auctions.exists()
    
    def add_random_assets(self, auction, eligible_assets, asset_count):
        selected_assets = sample(list(eligible_assets), asset_count)

        asset_slots = (
            constants.MORNING_ASSET_SLOTS if auction.time_period == 'morning'
            else constants.AFTERNOON_ASSET_SLOTS
        )[:asset_count]

        for asset, slot in zip(selected_assets, asset_slots):
            start_time, end_time = slot
            asset_start_at = timezone.make_aware(timezone.datetime.combine(auction.start_at.date(), timezone.datetime.strptime(start_time, '%H:%M:%S').time()))
            asset_end_at = timezone.make_aware(timezone.datetime.combine(auction.start_at.date(), timezone.datetime.strptime(end_time, '%H:%M:%S').time()))

            AuctionAsset.objects.create(
                auction=auction,
                asset=asset,
                start_at=asset_start_at,
                end_at=asset_end_at,
                starting_price=asset.appraised_value,
                current_price=asset.appraised_value
            )
            asset.status = AssetStatus.IN_AUCTION
            asset.save()

    @staticmethod
    def calculate_auction_dates(registration_start_date, time_period, asset_count):
        registration_start_at = timezone.make_aware(
            timezone.datetime.combine(
                registration_start_date, 
                timezone.datetime.strptime(constants.REGISTRATION_START_TIME, '%H:%M:%S').time()
            )
        )
        registration_end_at = registration_start_at + timezone.timedelta(days=constants.REGISTRATION_PERIOD - 1)
        registration_end_at = registration_end_at.replace(
            hour=timezone.datetime.strptime(constants.REGISTRATION_END_TIME, '%H:%M:%S').time().hour,
            minute=timezone.datetime.strptime(constants.REGISTRATION_END_TIME, '%H:%M:%S').time().minute,
            second=timezone.datetime.strptime(constants.REGISTRATION_END_TIME, '%H:%M:%S').time().second
        )

        auction_start_date = registration_end_at.date() + timezone.timedelta(days=constants.AUCTION_START_DELAY)

        if time_period == 'morning':
            asset_slots = constants.MORNING_ASSET_SLOTS[:asset_count]
        else:
            asset_slots = constants.AFTERNOON_ASSET_SLOTS[:asset_count]

        start_at = timezone.make_aware(timezone.datetime.combine(auction_start_date, timezone.datetime.strptime(asset_slots[0][0], '%H:%M:%S').time()))
        end_at = timezone.make_aware(timezone.datetime.combine(auction_start_date, timezone.datetime.strptime(asset_slots[-1][1], '%H:%M:%S').time()))

        return registration_start_at, registration_end_at, start_at, end_at

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        auction = self.get_object()
        now = timezone.now()
        
        if now >= auction.start_at and now < auction.end_at:
            auction.status = AuctionStatus.ACTIVE
        elif now >= auction.end_at:
            auction.status = AuctionStatus.FINISHED
            self.finalize_auction(auction)
        
        auction.save()
        return Response(AuctionSerializer(auction).data)

    def finalize_auction(self, auction):
        for auction_asset in auction.assets.all():
            highest_bid = auction_asset.bids.filter(is_current_highest=True).first()
            if highest_bid:
                auction_asset.final_price = highest_bid.amount
                auction_asset.asset.status = AssetStatus.SOLD
                auction_asset.asset.winner = highest_bid.user
                auction_asset.asset.save()
            else:
                auction_asset.asset.status = AssetStatus.PENDING
                auction_asset.asset.save()
            auction_asset.save()


class BidViewSet(viewsets.ModelViewSet):
    queryset = Bid.objects.all()
    serializer_class = BidSerializer
    permission_classes = [permissions.IsAuthenticated, CanPlaceBid]

    def perform_create(self, serializer):
        with transaction.atomic():
            bid = serializer.save(user=self.request.user)
            auction_asset = bid.auction_asset
            auction_asset.current_price = bid.amount
            auction_asset.bid_count += 1
            auction_asset.save()
            Bid.objects.filter(auction_asset=auction_asset).exclude(id=bid.id).update(is_current_highest=False)
            bid.is_current_highest = True
            bid.save()

    @action(detail=False, methods=['get'])
    def my_bids(self, request):
        bids = Bid.objects.filter(user=request.user)
        serializer = self.get_serializer(bids, many=True)
        return Response(serializer.data)

class RegistrationFeeViewSet(viewsets.ModelViewSet):
    queryset = RegistrationFee.objects.all()
    serializer_class = RegistrationFeeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        registration_fee = self.get_object()
        if registration_fee.registration_payment_status == PaymentStatus.PAID:
            return Response({"message": "Registration fee already paid."}, status=status.HTTP_400_BAD_REQUEST)
        registration_fee.registration_payment_status = PaymentStatus.PAID
        registration_fee.save()
        return Response(RegistrationFeeSerializer(registration_fee).data)

class AssetDepositViewSet(viewsets.ModelViewSet):
    queryset = AssetDeposit.objects.all()
    serializer_class = AssetDepositSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        asset_deposit = self.get_object()
        if asset_deposit.deposit_payment_status == PaymentStatus.PAID:
            return Response({"message": "Asset deposit already paid."}, status=status.HTTP_400_BAD_REQUEST)
        asset_deposit.deposit_payment_status = PaymentStatus.PAID
        asset_deposit.save()
        return Response(AssetDepositSerializer(asset_deposit).data)
    
class ContractViewSet(viewsets.ModelViewSet):
    queryset = Contract.objects.all()
    serializer_class = ContractSerializer
    permission_classes = [IsAdminUser | IsStaffUser]

    def perform_create(self, serializer):
        auction_asset = serializer.validated_data['auction_asset']
        if auction_asset.asset.status != AssetStatus.SOLD:
            raise ValidationError("Contract can only be created for sold assets.")

        winner = auction_asset.asset.winner
        seller = auction_asset.asset.seller

        if winner == seller:
            raise ValidationError("Winner and seller must be different users.")

        contract = serializer.save(
            winner=winner,
            seller=seller,
            status=ContractStatus.PENDING
        )
        contract.calculate_amounts()
        
    @action(detail=True, methods=['post'])
    def pay_winner(self, request, pk=None):
        contract = self.get_object()
        contract.winner_payment_status = PaymentStatus.PAID
        contract.save()
        contract.update_status()
        return Response(ContractSerializer(contract).data)

    @action(detail=True, methods=['post'])
    def pay_seller(self, request, pk=None):
        contract = self.get_object()
        contract.seller_payment_status = PaymentStatus.PAID
        contract.save()
        contract.update_status()
        return Response(ContractSerializer(contract).data)
    
class TaxViewSet(viewsets.ModelViewSet):
    queryset = Tax.objects.all()
    serializer_class = TaxSerializer
    permission_classes = [IsAdminUser | IsStaffUser]

class FeeViewSet(viewsets.ModelViewSet):
    queryset = Fee.objects.all()
    serializer_class = FeeSerializer
    permission_classes = [IsAdminUser | IsStaffUser]
    
class ContractTaxViewSet(viewsets.ModelViewSet):
    queryset = ContractTax.objects.all()
    serializer_class = ContractTaxSerializer
    permission_classes = [IsAdminUser | IsStaffUser]

class ContractFeeViewSet(viewsets.ModelViewSet):
    queryset = ContractFee.objects.all()
    serializer_class = ContractFeeSerializer
    permission_classes = [IsAdminUser | IsStaffUser]