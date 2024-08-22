from django_q.tasks import async_task
from assets.enums import AssetStatus
from django.utils import timezone
from .enums import AuctionStatus

def finalize_asset(auction_asset):
    highest_bid = auction_asset.bids.filter(
        is_current_highest=True).first()
    if highest_bid:
        auction_asset.final_price = highest_bid.amount
        auction_asset.asset.status = AssetStatus.SOLD
        auction_asset.asset.winner = highest_bid.user
    else:
        auction_asset.asset.status = AssetStatus.PENDING
    auction_asset.asset.save()
    auction_asset.save()

def schedule_finalize_asset(auction_asset, end_at):
    now = timezone.now()
    delay = (end_at - now).total_seconds()
    async_task('path.to.finalize_asset', auction_asset, q_options={'delay': delay})

def update_auction_status(auction):
    now = timezone.now()
    if now >= auction.registration_end_at and now <= auction.start_at:
        auction.status = AuctionStatus.UPCOMING
    elif now >= auction.start_at and now < auction.end_at:
        auction.status = AuctionStatus.ACTIVE
    elif now >= auction.end_at:
        auction.status = AuctionStatus.FINISHED
    auction.save()

def schedule_update_auction_status(auction, registration_end_at, start_at, end_at):
    now = timezone.now()
    delay_registration_end = (registration_end_at - now).total_seconds()
    delay_start = (start_at - now).total_seconds()
    delay_end = (end_at - now).total_seconds()

    async_task('path.to.update_auction_status', auction, q_options={'delay': delay_registration_end})
    async_task('path.to.update_auction_status', auction, q_options={'delay': delay_start})
    async_task('path.to.update_auction_status', auction, q_options={'delay': delay_end})
