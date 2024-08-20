from decimal import Decimal
from django.db import models
from users.models import User
from .enums import AssetStatus, AppraiserStatus, AssetAppraisalStatus, AssetMediaType, AssetCategory
from django.core.exceptions import ValidationError

class Appraiser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='appraiser_profile', primary_key=True)
    experiences = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=AppraiserStatus.choices, default=AppraiserStatus.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    update_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Appraiser: {self.user.first_name} {self.user.last_name}"


class Asset(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=100, choices=AssetCategory.choices)
    size = models.CharField(max_length=100)
    warehouse = models.CharField(max_length=255)
    origin = models.CharField(max_length=255)
    status = models.CharField(
        max_length=50, choices=AssetStatus.choices, default=AssetStatus.PENDING
    )

    quantity = models.PositiveIntegerField(default=1)
    seller = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="assets_for_sale"
    )
    winner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="won_assets",
    )
    appraiser = models.ForeignKey(
        Appraiser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appraised_assets",
    )
    appraise_status = models.CharField(
        max_length=50,
        choices=AssetAppraisalStatus.choices,
        default=AssetAppraisalStatus.NOT_APPRAISED,
    )
    appraised_value = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    appraisal_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    update_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


def asset_media_upload_to(instance, filename):
    return f"asset_media/{instance.asset.id}/{filename}"

class AssetMedia(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='media')
    media_type = models.CharField(max_length=20, choices=AssetMediaType.choices)
    file = models.FileField(upload_to=asset_media_upload_to)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
