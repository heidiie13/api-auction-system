from django.utils import timezone
from rest_framework import serializers

from assets.serializers import AssetSerializer
from .models import Auction, AuctionAsset, RegistrationFee, AssetDeposit, Bid, Fee, Tax, Contract, ContractFee, ContractTax
from .enums import AuctionStatus
from auctions import constants

class AuctionAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuctionAsset
        fields = ['id', 'auction', 'asset', 'start_at', 'end_at', 'starting_price', 'current_price',
                  'final_price', 'bid_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'starting_price', 'current_price',
                            'final_price', 'start_at', 'end_at', 'bid_count', 'created_at', 'updated_at']

class AuctionSerializer(serializers.ModelSerializer):
    time_period = serializers.ChoiceField(
        choices=constants.AUCTION_TIME_PERIODS, write_only=True)
    registration_start_date = serializers.DateField(write_only=True)

    class Meta:
        model = Auction
        fields = ['id', 'name', 'description', 'category', 'registration_start_date', 'time_period', 'registration_start_at', 'registration_end_at',
                  'start_at', 'end_at','status', 'created_at', 'updated_at']
        read_only_fields = ['id', 'registration_start_at', 'registration_end_at',
                            'start_at', 'end_at', 'auction_assets', 'created_at', 'updated_at']

    def validate_registration_start_date(self, value):
        if value <= timezone.now().date():
            raise serializers.ValidationError(
                "Registration start date must be in the future.")
        return value

    def create(self, validated_data):
        validated_data.pop('time_period')
        validated_data.pop('registration_start_date')
        return super().create(validated_data)


class RegistrationFeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistrationFee
        fields = ['id', 'user', 'auction', 'amount',
                  'registration_payment_status', 'created_at', 'updated_at']
        read_only_fields = [
            'id', 'registration_payment_status', 'created_at', 'updated_at']

    def validate_auction(self, value):
        user = self.context.get('user')
        if RegistrationFee.objects.filter(user=user, auction=value).exists():
            raise serializers.ValidationError("You have already registered for this auction.")
        if value.status != AuctionStatus.REGISTRATION:
            raise serializers.ValidationError(
                "Registration is not open for this auction.")
        return value

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive.")
        return value


class AssetDepositSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetDeposit
        fields = ['id', 'user', 'auction_asset', 'percentage', 'deposit_payment_status', 'amount',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'deposit_payment_status',
                            'amount', 'created_at', 'updated_at']

    def validate_percentage(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError(
                "Percentage must be between 0 and 100.")
        return value

    def validate_auction_asset(self, value):
        user = self.context.get('user')
        if AssetDeposit.objects.filter(user=user, auction_asset=value).exists():
            raise serializers.ValidationError("You have already deposited for this asset.")
        return value
    
    def create(self, validated_data):
        percentage = validated_data['percentage']
        auction_asset = validated_data['auction_asset']
        amount = (percentage / 100) * auction_asset.starting_price
        validated_data['amount'] = amount
        return super().create(validated_data)


class BidSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bid
        fields = ['id', 'user', 'auction_asset', 'amount',
                  'is_current_highest', 'created_at', 'updated_at']
        read_only_fields = ['id', 'is_current_highest',
                            'created_at', 'updated_at']


class FeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fee
        fields = ['id', 'name', 'fee_type', 'is_percentage',
                  'amount', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_amount(self, value):
        is_percentage = self.initial_data.get('is_percentage')
        if is_percentage and not 0 <= value <= 100:
                raise serializers.ValidationError(
                    "Percentage amount must be between 0 and 100.")
        else:
            if value < 0:
                raise serializers.ValidationError("Amount cannot be negative.")


class TaxSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tax
        fields = ['id', 'name', 'tax_type', 'is_percentage',
                  'amount', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_amount(self, value):
        is_percentage = self.initial_data.get('is_percentage')
        if isinstance(is_percentage, str):
            is_percentage = is_percentage.lower() in ['true', 't', '1']
        if is_percentage:
            if not 0 <= value <= 100:
                raise serializers.ValidationError("Percentage amount must be between 0 and 100.")
        else:
            if value < 0:
                raise serializers.ValidationError("Amount cannot be negative.")
        return value

class ContractFeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractFee
        fields = ['id', 'contract', 'fee',
                  'amount', 'created_at', 'updated_at']
        read_only_fields = ['id','amount', 'created_at', 'updated_at']

    def validate(self, attrs):
        if ContractFee.objects.filter(contract=attrs['contract'], fee=attrs['fee']).exists():
            raise serializers.ValidationError(
                "This fee has already been added to the contract.")
        return attrs

    def save(self, **kwargs):
        validated_data = self.validated_data
        fee = validated_data.get('fee')
        contract = validated_data.get('contract')
        if fee.is_percentage:
            validated_data['amount'] = (
                contract.final_price * fee.amount) / 100
        else:
            validated_data['amount'] = fee.amount
            
        instance = super().save(**kwargs)
        contract.calculate_amounts()
        return instance


class ContractTaxSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractTax
        fields = ['id', 'contract', 'tax',
                  'amount', 'created_at', 'updated_at']
        read_only_fields = ['id', 'amount', 'created_at', 'updated_at']

    def validate(self, attrs):
        if ContractTax.objects.filter(contract=attrs['contract'], tax=attrs['tax']).exists():
            raise serializers.ValidationError(
                "This tax has already been added to the contract.")
        return attrs

    def save(self, **kwargs):
        validated_data = self.validated_data
        tax = validated_data.get('tax')
        contract = validated_data.get('contract')
        if tax.is_percentage:
            validated_data['amount'] = (
                contract.final_price * tax.amount) / 100
        else:
            validated_data['amount'] = tax.amount
        
        instance = super().save(**kwargs)
        contract.calculate_amounts()
        return instance


class ContractSerializer(serializers.ModelSerializer):
    contract_fees = ContractFeeSerializer(many=True, read_only=True)
    contract_taxes = ContractTaxSerializer(many=True, read_only=True)
    asset = serializers.SerializerMethodField()

    class Meta:
        model = Contract
        fields = [
            'id', 'name', 'auction_asset', 'asset','winner', 'seller', 'status', 'contract_fees', 'contract_taxes',
            'winner_payment_status', 'seller_payment_status', 'payment_due_date',
            'created_at', 'updated_at', 'final_price', 'total_fees',
            'total_taxes', 'winner_amount_due', 'seller_amount_due'
        ]
        read_only_fields = [
            'id', 'status', 'winner', 'seller', 'winner_payment_status', 'seller_payment_status', 'created_at', 'updated_at', 'final_price',
            'total_fees', 'total_taxes', 'winner_amount_due', 'seller_amount_due'
        ]

    def get_asset(self, obj):
        if obj.auction_asset and obj.auction_asset.asset:
            return AssetSerializer(obj.auction_asset.asset).data
        return None

    def validate_payment_due_date(self, value):
        if value <= timezone.now().date():
            raise serializers.ValidationError(
                "Payment due date must be in the future.")
        return value
