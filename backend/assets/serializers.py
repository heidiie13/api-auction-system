from rest_framework import serializers
from assets.enums import AssetMediaType
from .models import Appraiser, Asset, AssetMedia


class AppraiserSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appraiser
        fields = ["id", "user", "experiences", "status", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class AssetMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetMedia
        fields = [
            "id",
            "asset",
            "media_type",
            "file",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_file_extension(self, file, valid_extensions):
        ext = file.name.split(".")[-1].lower()
        if ext not in valid_extensions:
            raise serializers.ValidationError(
                f"File extension '{ext}' is not allowed for this media type."
            )

    def validate(self, data):
        media_type = data.get("media_type")
        request = self.context.get("request")

        if not request or "file" not in request.FILES:
            raise serializers.ValidationError("No files provided.")

        files = request.FILES.getlist("file")

        if media_type == AssetMediaType.IMAGE:
            if len(files) != 1:
                raise serializers.ValidationError(
                    "For images, you must upload exactly 1 file."
                )
            valid_extensions = ["jpeg", "jpg", "png", "gif", "bmp", "tiff", "svg"]
        elif media_type == AssetMediaType.VIDEO:
            if len(files) != 1:
                raise serializers.ValidationError(
                    "For videos, you must upload exactly 1 file."
                )
            valid_extensions = ["mp4", "avi", "mov", "mkv", "wmv", "flv"]
        elif media_type == AssetMediaType.DOCUMENT:
            if len(files) != 1:
                raise serializers.ValidationError(
                    "For documents, you must upload exactly 1 file."
                )
            valid_extensions = [
                "doc",
                "docx",
                "pdf",
                "txt",
                "rtf",
                "odt",
                "ppt",
                "pptx",
                "xls",
                "xlsx",
            ]
        else:
            raise serializers.ValidationError("Invalid media type.")

        for file in files:
            self.validate_file_extension(file, valid_extensions)

        return data


class AssetSerializer(serializers.ModelSerializer):
    media = AssetMediaSerializer(many=True, read_only=True)

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
            "updated_at",
            "media",
            "quantity",
            "seller",
            "winner",
            "appraiser",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "appraise_status",
            "winner",
            "seller",
            "status",
            "appraised_value",
            "appraisal_at",
            "appraiser",
        ]


class AdminAssetSerializer(serializers.ModelSerializer):
    media = AssetMediaSerializer(many=True, read_only=True)

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
            "updated_at",
            "media",
            "quantity",
            "seller",
            "winner",
            "appraiser",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AssetAppraisalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = ["appraised_value"]

    def validate(self, data):
        if "appraised_value" not in data:
            raise serializers.ValidationError(
                "You must provide a value for appraised_value."
            )
        return data
