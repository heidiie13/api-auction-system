from django.utils import timezone
from rest_framework import serializers
from .models import Auction, AuctionAsset, RegistrationFee, AssetDeposit, Bid, Fee, Tax, Contract, ContractFee, ContractTax
from .enums import AuctionStatus, PaymentStatus
from assets.enums import AssetAppraisalStatus
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
    assets = AuctionAssetSerializer(many=True, read_only=True)
    
    class Meta:
        model = Auction
        fields = ['id', 'name', 'description','assets', 'registration_start_date', 'registration_start_at', 'registration_end_at',
                  'start_at', 'end_at', 'status', 'created_at', 'updated_at', 'time_period', 'category']
        read_only_fields = ['id', 'status', 'registration_start_at','registration_end_at', 'start_at', 'end_at','assets', 'created_at', 'updated_at']

    def validate_registration_start_date(self, value):
        if value <= timezone.now().date():
            raise serializers.ValidationError(
                "Registration start date must be in the future.")
        return value
    
class RegistrationFeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistrationFee
        fields = ['id', 'user', 'auction', 'amount',
                  'registration_payment_status', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def validate(self, attrs):
        if attrs['auction'].status != AuctionStatus.REGISTRATION:
            raise serializers.ValidationError(
                "Registration is not open for this auction.")
        return attrs

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive.")
        return value


class AssetDepositSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetDeposit
        fields = ['id', 'user', 'auction_asset', 'percentage', 'amount',
                  'deposit_payment_status', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'amount', 'created_at', 'updated_at']

    def validate(self, attrs):
        if attrs['auction_asset'].auction.status != AuctionStatus.REGISTRATION:
            raise serializers.ValidationError(
                "Deposit can only be made during the registration period.")
        if attrs['auction_asset'].asset.appraise_status != AssetAppraisalStatus.APPRAISAL_SUCCESSFUL:
            raise serializers.ValidationError(
                "Deposit can only be made for successfully appraised assets.")
        return attrs

    def save(self, **kwargs):
        validated_data = self.validated_data
        percentage = validated_data['percentage']
        auction_asset = validated_data['auction_asset']
        amount = (percentage / 100) * auction_asset.starting_price
        validated_data['amount'] = amount
        return super().save(**kwargs)


class BidSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bid
        fields = ['id', 'user', 'auction_asset', 'amount',
                  'is_current_highest', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user',
                            'is_current_highest', 'created_at', 'updated_at']

    def validate(self, attrs):
        auction_asset = attrs['auction_asset']
        if auction_asset.auction.status != AuctionStatus.ACTIVE:
            raise serializers.ValidationError(
                "Bidding is not allowed at this time.")
        if attrs['amount'] <= auction_asset.current_price:
            raise serializers.ValidationError(
                "Bid amount must be higher than the current price.")
        if not RegistrationFee.objects.filter(user=attrs['user'], auction=auction_asset.auction, registration_payment_status=PaymentStatus.PAID).exists():
            raise serializers.ValidationError(
                "You must pay the registration fee to place a bid.")
        if not AssetDeposit.objects.filter(user=attrs['user'], auction_asset=auction_asset, deposit_payment_status=PaymentStatus.PAID).exists():
            raise serializers.ValidationError(
                "You must pay the asset deposit to place a bid.")
        return attrs


class FeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fee
        fields = ['id', 'name', 'fee_type', 'is_percentage',
                  'amount', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        is_percentage = attrs['is_percentage']
        amount = attrs['amount']
        if is_percentage:
            if not 0 <= amount <= 100:
                raise serializers.ValidationError(
                    "Percentage amount must be between 0 and 100.")
        else:
            if amount < 0:
                raise serializers.ValidationError("Amount cannot be negative.")
        return attrs


class TaxSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tax
        fields = ['id', 'name', 'tax_type', 'is_percentage',
                  'amount', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        is_percentage = attrs['is_percentage']
        amount = attrs['amount']
        if is_percentage:
            if not 0 <= amount <= 100:
                raise serializers.ValidationError(
                    "Percentage amount must be between 0 and 100.")
        else:
            if amount < 0:
                raise serializers.ValidationError("Amount cannot be negative.")
        return attrs


class ContractFeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractFee
        fields = ['id', 'contract', 'fee',
                  'amount', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

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
        return super().save(**kwargs)


class ContractTaxSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractTax
        fields = ['id', 'contract', 'tax',
                  'amount', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

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
        return super().save(**kwargs)


class ContractSerializer(serializers.ModelSerializer):
    contract_fees = ContractFeeSerializer(many=True, read_only=True)
    contract_taxes = ContractTaxSerializer(many=True, read_only=True)

    class Meta:
        model = Contract
        fields = [
            'id', 'name', 'auction_asset', 'winner', 'seller', 'status', 'contract_fees', 'contract_taxes',
            'winner_payment_status', 'seller_payment_status', 'payment_due_date',
            'created_at', 'updated_at', 'final_price', 'total_fees',
            'total_taxes', 'winner_amount_due', 'seller_amount_due'
        ]
        read_only_fields = [
            'id', 'status', 'winner', 'seller', 'created_at', 'updated_at', 'final_price',
            'total_fees', 'total_taxes', 'winner_amount_due', 'seller_amount_due'
        ]

    def validate_payment_due_date(self, value):
        if value <= timezone.now().date():
            raise serializers.ValidationError(
                "Payment due date must be in the future.")
        return value
