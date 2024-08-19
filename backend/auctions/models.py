from decimal import Decimal
from django.db import models
from django.utils import timezone
from users.models import User
from assets.models import Asset
from .enums import AuctionStatus, FeeType, ContractStatus, PaymentStatus, TaxType
from assets.enums import AssetCategory

class Auction(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    registration_start_at = models.DateTimeField()
    registration_end_at = models.DateTimeField()
    category = models.CharField(max_length=100, choices=AssetCategory.choices)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=AuctionStatus.choices, default=AuctionStatus.REGISTRATION)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class AuctionAsset(models.Model):
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name='assets')
    asset = models.OneToOneField(Asset, on_delete=models.CASCADE, related_name='auction_entry')
    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)
    starting_price = models.DecimalField(max_digits=12, decimal_places=2)
    current_price = models.DecimalField(max_digits=12, decimal_places=2)
    final_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    bid_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.asset.name} in {self.auction.name}"

class RegistrationFee(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='registration_fees')
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name='registration_fees')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    registration_payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'auction')
        
class AssetDeposit(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='deposits')
    auction_asset = models.ForeignKey(AuctionAsset, on_delete=models.CASCADE, related_name='deposits')
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    deposit_payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'auction_asset')

    def __str__(self):
        return f"Deposit for {self.auction_asset.asset.name} by {self.user}"
    
class Bid(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bids')
    auction_asset = models.ForeignKey(AuctionAsset, on_delete=models.CASCADE, related_name='bids')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_current_highest = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'auction_asset')
        
    def __str__(self):
        return f"Bid of {self.amount} by {self.user} for {self.auction_asset.asset.name}"

class Fee(models.Model):
    name = models.CharField(max_length=255)
    fee_type = models.CharField(max_length=50, choices=FeeType.choices)
    is_percentage = models.BooleanField(default=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_fee_type_display()})"
        
class Tax(models.Model):
    name = models.CharField(max_length=255)
    tax_type = models.CharField(max_length=50, choices=TaxType.choices)
    is_percentage = models.BooleanField(default=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_tax_type_display()})"
    
class Contract(models.Model):
    name = models.CharField(max_length=255)
    auction_asset = models.OneToOneField(AuctionAsset, on_delete=models.CASCADE, related_name='contract')
    winner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='won_contracts')
    seller = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sold_contracts')
    status = models.CharField(max_length=20, choices=ContractStatus.choices, default=ContractStatus.PENDING)
    total_fees = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_taxes = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    winner_amount_due = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    seller_amount_due = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    winner_payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID)
    seller_payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID)
    payment_due_date = models.DateField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def update_status(self):
        if self.winner_payment_status == PaymentStatus.PAID and self.seller_payment_status == PaymentStatus.PAID:
            self.status = ContractStatus.COMPLETED
        self.save()
        
    def calculate_amounts(self):
        self.total_fees = sum(cf.amount for cf in self.contract_fees.all())
        self.total_taxes = sum(ct.amount for ct in self.contract_taxes.all())
        self.winner_amount_due = self.auction_asset.final_price + self.total_taxes - self.winner.deposits.amount
        self.seller_amount_due = self.total_fees
        self.save()

    @property
    def final_price(self):
        return self.auction_asset.final_price

    def __str__(self):
        return f"Contract for {self.auction_asset.asset.name}"
    
class ContractFee(models.Model):
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='contract_fees')
    fee = models.ForeignKey(Fee, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.fee} for {self.contract}"

class ContractTax(models.Model):
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='contract_taxes')
    tax = models.ForeignKey(Tax, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.tax} for {self.contract}"