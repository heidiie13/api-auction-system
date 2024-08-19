from django.db import models

class AuctionStatus(models.TextChoices):
    REGISTRATION = 'registration', 'Registration'
    UPCOMING = 'upcoming', 'Upcoming'
    ACTIVE = 'active', 'Active'
    FINISHED = 'finished', 'Finished'
    CANCELLED = 'cancelled', 'Cancelled'

class ContractStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    ACTIVE = 'active', 'Active'
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'

class PaymentStatus(models.TextChoices):
    UNPAID = 'unpaid', 'Unpaid'
    PAID = 'paid', 'Paid'
    
class TaxType(models.TextChoices):
    IMPORT = 'import', 'Import Tax'
    VAT = 'vat', 'Value Added Tax'
    INCOME = 'income', 'Personal Income Tax'
    SALES = 'sales', 'Sales Tax'

class FeeType(models.TextChoices):
    COMMISSION = 'commission', 'Commission Fee'
    LISTING = 'listing', 'Listing Fee'
    INSURANCE = 'insurance', 'Insurance Fee'
    SHIPPING = 'shipping', 'Shipping Fee'
    OTHER = 'other', 'Other Service Fee'