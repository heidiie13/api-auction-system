from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from users.models import User
from assets.models import Asset
from assets.enums import AssetStatus, AssetAppraisalStatus
from .enums import AuctionStatus, FeeType, ContractStatus, PaymentStatus, TransactionStatus, TransactionType, TaxType

class Auction(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=AuctionStatus.choices, default=AuctionStatus.UPCOMING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.end_at <= self.start_at:
            raise ValidationError("End time must be after start time.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def update_status(self):
        now = timezone.now()
        if self.start_at <= now < self.end_at:
            self.status = AuctionStatus.ACTIVE
        elif now >= self.end_at:
            self.status = AuctionStatus.FINISHED
        self.save()

    def __str__(self):
        return self.name

class AuctionAsset(models.Model):
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name='assets')
    asset = models.OneToOneField(Asset, on_delete=models.CASCADE, related_name='auction_entry')
    starting_price = models.DecimalField(max_digits=12, decimal_places=2)
    current_price = models.DecimalField(max_digits=12, decimal_places=2)
    final_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    bid_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.asset.appraise_status != AssetAppraisalStatus.APPRAISAL_SUCCESSFUL:
            raise ValidationError("Only successfully appraised assets can be added to an auction.")
        if self.asset.status != AssetStatus.PENDING:
            raise ValidationError("Only pending assets can be added to an auction.")

    def save(self, *args, **kwargs):
        if not self.starting_price:
            self.starting_price = self.asset.appraised_value
        if not self.current_price:
            self.current_price = self.starting_price
        self.full_clean()
        super().save(*args, **kwargs)
        if self.final_price:
            self.asset.status = AssetStatus.SOLD
            self.asset.save()

    def __str__(self):
        return f"{self.asset.name} in {self.auction.name}"

class AssetDeposit(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='deposits')
    auction_asset = models.ForeignKey(AuctionAsset, on_delete=models.CASCADE, related_name='deposits')
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'auction_asset')

    def __str__(self):
        return f"Deposit for {self.auction_asset.asset.name} by {self.user}"

    def save(self, *args, **kwargs):
        self.amount = (self.percentage / 100) * self.auction_asset.starting_price
        super().save(*args, **kwargs)
    
class Bid(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bids')
    auction_asset = models.ForeignKey(AuctionAsset, on_delete=models.CASCADE, related_name='bids')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_current_highest = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-amount']
        
    def clean(self):
        if self.amount <= self.auction_asset.current_price:
            raise ValidationError("Bid amount must be higher than current price.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

        if self.is_current_highest:
            self.auction_asset.current_price = self.amount
            self.auction_asset.save()
            Bid.objects.filter(auction_asset=self.auction_asset).exclude(pk=self.pk).update(is_current_highest=False)
            
    def __str__(self):
        return f"Bid of {self.amount} by {self.user.username} for {self.auction_asset.asset.name}"

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
        
    def clean(self):
        if self.is_percentage and (self.amount < 0 or self.amount > 100):
            raise ValidationError("Percentage amount must be between 0 and 100.")
        if not self.is_percentage and self.amount < 0:
            raise ValidationError("Amount cannot be negative.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        
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
    
    def clean(self):
        if self.is_percentage and (self.amount < 0 or self.amount > 100):
            raise ValidationError("Percentage amount must be between 0 and 100.")
        if not self.is_percentage and self.amount < 0:
            raise ValidationError("Amount cannot be negative.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

class Contract(models.Model):
    name = models.CharField(max_length=255)
    auction_asset = models.OneToOneField(AuctionAsset, on_delete=models.CASCADE, related_name='contract')
    winner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='won_contracts')
    seller = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sold_contracts')
    status = models.CharField(max_length=20, choices=ContractStatus.choices, default=ContractStatus.PENDING)
    tax_payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID)
    fee_payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID)
    payment_due_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def update_status(self):
        if self.tax_payment_status == PaymentStatus.PAID and self.fee_payment_status == PaymentStatus.PAID:
            self.status = ContractStatus.COMPLETED
        self.save()
        
    @property
    def final_price(self):
        return self.auction_asset.final_price

    @property
    def total_fees(self):
        return sum(cf.amount for cf in self.contract_fees.all())

    @property
    def total_taxes(self):
        return sum(ct.amount for ct in self.contract_taxes.all())
    
    @property
    def winner_amount_due(self):
        return self.final_price + self.total_taxes

    @property
    def seller_amount_due(self):
        return self.total_fees

    @property
    def total_amount_due(self):
        return self.winner_amount_due + self.seller_amount_due
    
    def __str__(self):
        return f"Contract for {self.auction_asset.asset.name}"
        
class ContractFee(models.Model):
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='contract_fees')
    fee = models.ForeignKey(Fee, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def calculate_amount(self):
        if self.fee.is_percentage:
            return (self.contract.final_price * self.fee.amount) / 100
        return self.fee.amount
    
    def update_amount(self):
        self.amount = self.calculate_amount()
        self.save()
        
    def __str__(self):
        return f"{self.fee} for {self.contract}"

class ContractTax(models.Model):
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='contract_taxes')
    tax = models.ForeignKey(Tax, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def calculate_amount(self):
        if self.tax.is_percentage:
            return (self.contract.final_price * self.tax.amount) / 100
        return self.tax.amount
    
    def update_amount(self):
        self.amount = self.calculate_amount()
        self.save()
        
    def __str__(self):
        return f"{self.tax} for {self.contract}"

    
class TransactionHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    status = models.CharField(max_length=20, choices=TransactionStatus.choices, default=TransactionStatus.PENDING)
    description = models.TextField()
    contract = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    auction = models.ForeignKey(Auction, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    auction_asset = models.ForeignKey(AuctionAsset, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.transaction_type} - {self.user.email}"