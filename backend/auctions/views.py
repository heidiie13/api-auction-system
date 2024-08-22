from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import OrderingFilter
from rest_framework.exceptions import ValidationError

from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend

from .models import Auction, AuctionAsset, RegistrationFee, AssetDeposit, Bid, Contract, Tax, Fee, ContractTax, ContractFee
from .serializers import (
    AssetDepositSerializer, AuctionAssetSerializer, AuctionSerializer, BidSerializer, ContractSerializer, RegistrationFeeSerializer, TaxSerializer, FeeSerializer, ContractFeeSerializer, ContractTaxSerializer
)
from .enums import AuctionStatus, PaymentStatus, ContractStatus
from .permissions import IsSeller, IsWinner
from .tasks import schedule_finalize_asset, schedule_update_auction_status
from assets.enums import AssetStatus
from assets.models import Asset, AssetAppraisalStatus
from users.permissions import IsStaffUser
from auctions import constants

from random import sample
from datetime import datetime


class AuctionViewSet(viewsets.ModelViewSet):
    queryset = Auction.objects.all()
    serializer_class = AuctionSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'category']
    ordering_fields = ['registration_start_at', 'start_at', 'end_at']
    ordering = ['-registration_start_at']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsStaffUser]
        else:
            permission_classes = [permissions.AllowAny]
        return [permission() for permission in permission_classes]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        time_period = serializer.validated_data.get('time_period')
        registration_start_date = serializer.validated_data.get(
            'registration_start_date')
        category = serializer.validated_data.get('category')

        eligible_assets = Asset.objects.filter(
            Q(category=category) &
            Q(appraise_status=AssetAppraisalStatus.APPRAISAL_SUCCESSFUL) &
            Q(status=AssetStatus.PENDING)
        )

        asset_count = min(eligible_assets.count(), 3)
        if asset_count < 1:
            return Response({"error": "Not enough eligible assets to create an auction."}, status=status.HTTP_400_BAD_REQUEST)

        registration_start_at, registration_end_at, start_at, end_at = self.calculate_auction_dates(
            registration_start_date, time_period, asset_count
        )
        with transaction.atomic():
            if self.is_auction_slot_available(start_at, end_at):
                auction = serializer.save(
                    registration_start_at=registration_start_at,
                    registration_end_at=registration_end_at,
                    start_at=start_at,
                    end_at=end_at,
                    status=AuctionStatus.REGISTRATION
                )
                self.add_random_assets(auction, eligible_assets, asset_count)
                schedule_update_auction_status(
                    auction, registration_end_at, start_at, end_at)
            else:
                return Response({"error": "There is already an auction scheduled for this time period."}, status=status.HTTP_409_CONFLICT)

            headers = self.get_success_headers(serializer.data)

            return Response({
                "message": "Auction created successfully.",
                "auction": serializer.data
            }, status=status.HTTP_201_CREATED, headers=headers)

    def destroy(self, request, *args, **kwargs):
        auction = self.get_object()

        if timezone.now() >= auction.start_at:
            return Response(
                {"error": "Cannot delete an auction that has already started."},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            auction_assets = AuctionAsset.objects.filter(auction=auction)

            for auction_asset in auction_assets:
                auction_asset.asset.status = AssetStatus.PENDING
                auction_asset.asset.save()

            response = super().destroy(request, *args, **kwargs)

        return response

    def is_auction_slot_available(self, start_at, end_at):
        overlapping_auctions = Auction.objects.filter(
            Q(start_at__lt=end_at) & Q(end_at__gt=start_at)
        )
        return not overlapping_auctions.exists()

    def add_random_assets(self, auction, eligible_assets, asset_count):
        selected_assets = sample(list(eligible_assets), asset_count)

        asset_slots = (
            constants.MORNING_ASSET_SLOTS if self.request.data.get('time_period') == 'morning'
            else constants.AFTERNOON_ASSET_SLOTS
        )[:asset_count]

        with transaction.atomic():
            for asset, slot in zip(selected_assets, asset_slots):
                start_time, end_time = slot
                asset_start_at = timezone.make_aware(timezone.datetime.combine(
                    auction.start_at.date(), timezone.datetime.strptime(start_time, '%H:%M:%S').time()))
                asset_end_at = timezone.make_aware(timezone.datetime.combine(
                    auction.start_at.date(), timezone.datetime.strptime(end_time, '%H:%M:%S').time()))

            try:
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
            except Exception as e:
                raise ValidationError(f"Failed to add asset: {str(e)}")

    @staticmethod
    def calculate_auction_dates(registration_start_date, time_period, asset_count):
        registration_start_at = timezone.make_aware(
            datetime.combine(
                registration_start_date,
                datetime.strptime(
                    constants.REGISTRATION_START_TIME, '%H:%M:%S').time()
            )
        )
        registration_end_at = registration_start_at + \
            timezone.timedelta(days=constants.REGISTRATION_PERIOD - 1)
        registration_end_at = registration_end_at.replace(
            hour=datetime.strptime(
                constants.REGISTRATION_END_TIME, '%H:%M:%S').time().hour,
            minute=datetime.strptime(
                constants.REGISTRATION_END_TIME, '%H:%M:%S').time().minute,
            second=datetime.strptime(
                constants.REGISTRATION_END_TIME, '%H:%M:%S').time().second
        )

        auction_start_date = registration_end_at.date(
        ) + timezone.timedelta(days=constants.AUCTION_START_DELAY)

        if time_period == 'morning':
            asset_slots = constants.MORNING_ASSET_SLOTS[:asset_count]
        else:
            asset_slots = constants.AFTERNOON_ASSET_SLOTS[:asset_count]

        start_at = timezone.make_aware(datetime.combine(
            auction_start_date,
            datetime.strptime(asset_slots[0][0], '%H:%M:%S').time()
        ))
        end_at = timezone.make_aware(datetime.combine(
            auction_start_date,
            datetime.strptime(asset_slots[-1][1], '%H:%M:%S').time()
        ))

        return registration_start_at, registration_end_at, start_at, end_at

class AuctionAssetReadViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuctionAssetSerializer

    def get_queryset(self):
        auction_id = self.kwargs.get('auction_pk')
        auction = get_object_or_404(Auction, id=auction_id)
        return AuctionAsset.objects.filter(auction=auction)

class AuctionAssetViewSet(viewsets.ModelViewSet):
    serializer_class = AuctionAssetSerializer
    queryset = AuctionAsset.objects.all()
    permission_classes = [IsStaffUser]
    
class BidViewSet(viewsets.ModelViewSet):
    serializer_class = BidSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['auction_asset']
    ordering_fields = ['amount', 'created_at']
    ordering = ['-amount']

    def get_permissions(self):
        if self.action in ['create', 'list', 'retrieve']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [IsStaffUser]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            return Bid.objects.filter(user=user)
        if user.is_staff or user.is_superuser:
            return Bid.objects.all()
        return Bid.objects.none()

    def create(self, request, *args, **kwargs):
        user = self.request.user
        serializer = self.get_serializer(data={'user':user.id,**request.data})
        serializer.is_valid(raise_exception=True)
    
        auction_asset = serializer.validated_data['auction_asset']
        amount = serializer.validated_data['amount']
        
        if auction_asset.auction.status != AuctionStatus.ACTIVE:
            return Response({"error": "Bidding is not allowed at this time."}, status=status.HTTP_400_BAD_REQUEST)

        if not AssetDeposit.objects.filter(user=user, auction_asset=auction_asset, deposit_payment_status=PaymentStatus.PAID).exists():
            return Response({"error": "You must pay the asset deposit to place a bid."}, status=status.HTTP_400_BAD_REQUEST)

        if amount <= auction_asset.current_price:
            return Response({"error": "Bid amount must be higher than the current price."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            bid = serializer.save()
            auction_asset.current_price = bid.amount
            auction_asset.bid_count += 1
            auction_asset.save()
            Bid.objects.filter(auction_asset=auction_asset).exclude(
                id=bid.id).update(is_current_highest=False)
            bid.is_current_highest = True
            bid.save()
            schedule_finalize_asset(auction_asset, auction_asset.end_at)
            
        return Response({"message": "Bid created successfully", "bid":serializer.data}, status=status.HTTP_201_CREATED)


class RegistrationFeeViewSet(viewsets.ModelViewSet):
    queryset = RegistrationFee.objects.all()
    serializer_class = RegistrationFeeSerializer

    def get_permissions(self):
        if self.action in ['create', 'list', 'retrieve', 'pay']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [IsStaffUser]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        if self.request.user.is_staff:
            return super().get_queryset()
        return super().get_queryset().filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        user = request.user
        serializer = self.get_serializer(
            data={'user': user.id, 'amount': constants.REGISTRATION_FEE, **request.data}, context={'user': self.request.user})
        serializer.is_valid(raise_exception=True)

        serializer.save()
        auction = serializer.validated_data['auction']

        if auction.status != AuctionStatus.REGISTRATION:
            return Response({"error": "Registration is not open for this auction."}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "message": "Registration successful. Please proceed to pay the registration fee.",
            "registration_fee": serializer.data
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        registration_fee = self.get_object()

        if registration_fee.registration_payment_status == PaymentStatus.PAID:
            return Response({"error": "Registration fee already paid."}, status=status.HTTP_400_BAD_REQUEST)

        registration_fee.registration_payment_status = PaymentStatus.PAID
        registration_fee.save()

        serializer = self.get_serializer(registration_fee)

        return Response({"message": "Registration fee paid successfully.", "registration_fee": serializer.data}, status=status.HTTP_200_OK)


class AssetDepositViewSet(viewsets.ModelViewSet):
    queryset = AssetDeposit.objects.all()
    serializer_class = AssetDepositSerializer

    def get_permissions(self):
        if self.action in ['create', 'list', 'retrieve', 'pay']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [IsStaffUser]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        if self.request.user.is_staff:
            return super().get_queryset()
        return super().get_queryset().filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        user = request.user
        auction_asset_id = request.data.get('auction_asset')

        errors = {}
        if not auction_asset_id:
            errors['auction_asset'] = "This field is required."
        
        if errors:
            raise ValidationError(errors)
        
        try:
            auction_asset = AuctionAsset.objects.get(pk=auction_asset_id)
        except AuctionAsset.DoesNotExist:
            return Response({"error": "Auction asset not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(data={'user': user.id, 'percentage': constants.DEPOSIT_PERCENTAGES.get(
            auction_asset.asset.category, 0), **request.data}, context={'user': self.request.user})
        serializer.is_valid(raise_exception=True)

        if auction_asset.auction.status != AuctionStatus.REGISTRATION:
            return Response({"error": "Deposit can only be made during the registration period."}, status=status.HTTP_400_BAD_REQUEST)
        if auction_asset.asset.appraise_status != AssetAppraisalStatus.APPRAISAL_SUCCESSFUL:
            return Response({"error": "Deposit can only be made for successfully appraised assets."}, status=status.HTTP_400_BAD_REQUEST)

        registration_fee = RegistrationFee.objects.filter(user=user, auction=auction_asset.auction).first()
        if not registration_fee or registration_fee.registration_payment_status != PaymentStatus.PAID:
            return Response({"error": "You must pay the registration fee before making a deposit."}, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()

        return Response({
            "message": "Deposit successful. Please proceed to pay the deposit.",
            "deposit": serializer.data
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        asset_deposit = self.get_object()

        if asset_deposit.deposit_payment_status == PaymentStatus.PAID:
            return Response({"error": "Deposit already paid."}, status=status.HTTP_400_BAD_REQUEST)

        asset_deposit.deposit_payment_status = PaymentStatus.PAID
        asset_deposit.save()

        serializer = self.get_serializer(asset_deposit)

        return Response({"message": "Deposit paid successfully.", "deposit": serializer.data}, status=status.HTTP_200_OK)


class ContractViewSet(viewsets.ModelViewSet):
    serializer_class = ContractSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Contract.objects.all()
        return Contract.objects.filter(Q(sell=user)|Q(winner=user)) 
    
    def get_permissions(self):
        if self.action in ['list','retrieve']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [IsStaffUser]
        return [permission() for permission in permission_classes]       
     
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        auction_asset = serializer.validated_data['auction_asset']
        if auction_asset.asset.status != AssetStatus.SOLD:
            return Response({"error": "Contract can only be created for sold assets."}, status=status.HTTP_400_BAD_REQUEST)

        winner = auction_asset.asset.winner
        seller = auction_asset.asset.seller

        with transaction.atomic():
            serializer.save(
                winner=winner,
                seller=seller,
                status=ContractStatus.ACTIVE
            )

        return Response({
            "message": "Contract created successful.",
            "contract": serializer.data
        },status=status.HTTP_201_CREATED)
        
    @action(detail=True, methods=['post'], permission_classes=[IsWinner], url_path='pay-winner')
    def pay_winner(self, request, pk=None):
        contract = self.get_object()
        contract.winner_payment_status = PaymentStatus.PAID
        contract.save()
        contract.update_status()
        return Response({
            "message": "Winner payment successful.",
            "contract": ContractSerializer(contract).data
        })


    @action(detail=True, methods=['post'], permission_classes=[IsSeller], url_path='pay-seller')
    def pay_seller(self, request, pk=None):
        contract = self.get_object()
        contract.seller_payment_status = PaymentStatus.PAID
        contract.save()
        contract.update_status()
        return Response({
            "message": "Seller payment successful.",
            "contract": ContractSerializer(contract).data
        })


class TaxViewSet(viewsets.ModelViewSet):
    queryset = Tax.objects.all()
    serializer_class = TaxSerializer
    permission_classes = [IsStaffUser]

class FeeViewSet(viewsets.ModelViewSet):
    queryset = Fee.objects.all()
    serializer_class = FeeSerializer
    permission_classes = [IsStaffUser]

class ContractTaxViewSet(viewsets.ModelViewSet):
    queryset = ContractTax.objects.all()
    serializer_class = ContractTaxSerializer
    permission_classes = [IsStaffUser]

class ContractFeeViewSet(viewsets.ModelViewSet):
    queryset = ContractFee.objects.all()
    serializer_class = ContractFeeSerializer
    permission_classes = [IsStaffUser]