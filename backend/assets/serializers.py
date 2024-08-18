from rest_framework import serializers
from .models import Appraiser, Asset, AssetMedia
from .enums import AssetMediaType

class AppraiserSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appraiser
        fields = ["user_id", "experiences", "status", "created_at", "update_at"]
        read_only_fields = ["user_id", "created_at", "update_at"]


class AssetMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetMedia
        fields = [
            "id",
            "asset",
            "media_type",
            "file",
            "is_primary",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AssetSerializer(serializers.ModelSerializer):
    media = AssetMediaSerializer(many=True, read_only=True)
    seller_id = serializers.PrimaryKeyRelatedField(read_only=True)
    winner_id = serializers.PrimaryKeyRelatedField(read_only=True)
    appraiser_id = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Asset
        fields = [
            "id",
            "name",
            "description",
            "category",
            "size",
            "warehouse",
            "origin",
            "status",
            "appraise_status",
            "appraised_value",
            "appraisal_at",
            "created_at",
            "update_at",
            "media",
            "quantity",
            "seller_id",
            "winner_id",
            "appraiser_id",
        ]
        read_only_fields = ["id", "created_at", "update_at"]
