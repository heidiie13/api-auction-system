from django.core.exceptions import ValidationError

from rest_framework import serializers
from .models import Auction, AuctionAsset, AssetDeposit, Bid, Fee, Tax, Contract, ContractFee, ContractTax, TransactionHistory

class AuctionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Auction
        fields = ['id', 'name', 'description', 'start_at', 'end_at', 'status', 'max_assets', 'created_at', 'updated_at']
        read_only_fields = ['id', 'status', 'created_at', 'updated_at']

class AuctionAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuctionAsset
        fields = ['id', 'auction', 'asset', 'starting_price', 'current_price', 'final_price', 'bid_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'starting_price', 'current_price', 'final_price', 'bid_count', 'created_at', 'updated_at']

class AssetDepositSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetDeposit
        fields = ['id', 'user', 'auction_asset', 'amount', 'is_approved', 'created_at', 'updated_at']
        read_only_fields = ['id', 'is_approved', 'created_at', 'updated_at']

class BidSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bid
        fields = ['id', 'user', 'auction_asset', 'amount', 'is_current_highest', 'created_at', 'updated_at']
        read_only_fields = ['id', 'is_current_highest', 'created_at', 'updated_at']

class FeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fee
        fields = ['id', 'name', 'fee_type', 'is_percentage', 'amount', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id','created_at', 'updated_at']

class TaxSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tax
        fields = ['id', 'name', 'tax_type', 'is_percentage', 'amount', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id','created_at', 'updated_at']

class ContractSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = ['id', 'name', 'auction_asset', 'winner', 'seller', 'status', 'tax_payment_status', 'fee_payment_status', 'payment_due_date', 'created_at', 'updated_at', 'final_price', 'total_fees', 'total_taxes', 'winner_amount_due', 'seller_amount_due', 'total_amount_due']
        read_only_fields = ['id','status', 'tax_payment_status', 'fee_payment_status', 'created_at', 'updated_at', 'final_price', 'total_fees', 'total_taxes', 'winner_amount_due', 'seller_amount_due', 'total_amount_due']

class ContractFeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractFee
        fields = ['id', 'contract', 'fee', 'amount', 'created_at', 'updated_at']
        read_only_fields = ['id','amount', 'created_at', 'updated_at']

class ContractTaxSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractTax
        fields = ['id', 'contract', 'tax', 'amount', 'created_at', 'updated_at']
        read_only_fields = ['id','amount', 'created_at', 'updated_at']

class TransactionHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionHistory
        fields = ['id', 'user', 'amount', 'transaction_type', 'status', 'description', 'sender', 'recipient', 'auction', 'auction_asset', 'note', 'created_at', 'updated_at']
        read_only_fields = ['id','created_at', 'updated_at']