from django.contrib import admin
from .models import Auction, AuctionItem, AuctionParticipant, Bid, Contract, Fee, Tax, ContractTax, TransactionHistory

admin.site.register(Auction)
admin.site.register(AuctionItem)
admin.site.register(AuctionParticipant)
admin.site.register(ContractTax)
admin.site.register(TransactionHistory)
admin.site.register(Bid)
admin.site.register(Fee)
admin.site.register(Contract)
admin.site.register(Tax)