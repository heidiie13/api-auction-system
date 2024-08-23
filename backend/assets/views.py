from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from assets.permissions import (
    AssetMediaPermission,
    AssetPermission,
)
from .models import Asset, Appraiser, AssetMedia
from .serializers import (
    AdminAssetSerializer,
    AppraiserSerializer,
    AssetMediaSerializer,
    AssetReadOnlySerializer,
    AssetSerializer,
    AssetAppraisalSerializer,
)
from .enums import AssetMediaType, AssetStatus, AppraiserStatus, AssetAppraisalStatus
from users.permissions import IsStaffUser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import PermissionDenied, ValidationError


class AssetReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Asset.objects.filter(status=AssetStatus.IN_AUCTION)
    serializer_class = AssetReadOnlySerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ["category", "status"]
    ordering_fields = ["created_at", "name", "updated_at"]
    ordering = ["-created_at"]
    search_fields = ["name"]

class AssetViewSet(viewsets.ModelViewSet):
    queryset = Asset.objects.all()
    serializer_class = AssetSerializer
    permission_classes = [AssetPermission]
    filter_backends = [DjangoFilterBackend,
                       filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ["category", "status"]
    ordering_fields = ["created_at", "name", "updated_at"]
    ordering = ["-created_at"]
    search_fields = ["name"]

    def get_serializer_class(self):
        if self.request.user.is_staff or self.request.user.is_superuser:
            return AdminAssetSerializer
        return AssetSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Asset.objects.none()
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Asset.objects.all()
        if hasattr(user, 'appraiser_profile'):
            return Asset.objects.filter(appraiser=user.appraiser_profile)
        return Asset.objects.filter(seller=user)

    def create(self, request, *args, **kwargs):
        user = self.request.user
        serializer = self.get_serializer(
            data={"seller": user.id, **request.data})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response({"message": "Asset created successfull", "asset": serializer.data}, status=status.HTTP_201_CREATED, headers=headers)
    def perform_create(self, serializer):
        return serializer.save(seller=self.request.user)
    
    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated], url_path="register-for-auction"
    )
    def register_for_auction(self, request, pk=None):
        asset = self.get_object()
        if (
            asset.appraise_status != AssetAppraisalStatus.NOT_APPRAISED
            and asset.status != AssetStatus.PENDING
        ):
            return Response(
                {"error": "This asset is not available for auction registration."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        appraiser = Appraiser.objects.filter(
            status=AppraiserStatus.ACTIVE).first()

        if not appraiser:
            return Response(
                {"error": "No inactive appraiser available."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if asset.appraiser:
            return Response(
                {"error": "This asset already has an appraiser assigned.",
                    "appraiser": AppraiserSerializer(appraiser).data},
                status=status.HTTP_400_BAD_REQUEST,
            )

        asset.appraise_status = AssetAppraisalStatus.UNDER_APPRAISAL
        asset.appraiser = appraiser
        asset.save()

        appraiser.status = AppraiserStatus.INACTIVE
        appraiser.save()

        return Response(
            {"message": "Asset registered for auction and appraiser assigned.",
                "appraiser": AppraiserSerializer(appraiser).data},
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated],
        serializer_class=AssetAppraisalSerializer, url_path="update-appraisal"
    )
    def update_appraisal(self, request, pk=None):
        asset = self.get_object()
        try:
            current_appraiser = request.user.appraiser_profile
        except Appraiser.DoesNotExist:
            return Response({"error": "You are not an appraiser."}, status=status.HTTP_403_FORBIDDEN)

        if asset.appraiser != current_appraiser:
            return Response({"error": "You are not the assigned appraiser for this asset."}, status=status.HTTP_403_FORBIDDEN)

        if asset.appraise_status in [
            AssetAppraisalStatus.APPRAISAL_SUCCESSFUL,
            AssetAppraisalStatus.APPRAISAL_FAILED,
        ]:
            return Response(
                {
                    "error": "This asset's appraisal has been completed and cannot be modified."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if asset.status != AssetStatus.PENDING:
            return Response(
                {"error": "This asset cannot be modified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AssetAppraisalSerializer(asset, data=request.data)
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated], url_path="complete-appraisal-successful"
    )
    def complete_appraisal_successful(self, request, pk=None):
        asset = self.get_object()
        try:
            current_appraiser = request.user.appraiser_profile
        except Appraiser.DoesNotExist:
            return Response({"error": "You are not an appraiser."}, status=status.HTTP_403_FORBIDDEN)

        if asset.appraiser != current_appraiser:
            return Response({"error": "You are not the assigned appraiser for this asset."}, status=status.HTTP_403_FORBIDDEN)

        if asset.appraise_status == AssetAppraisalStatus.APPRAISAL_SUCCESSFUL:
            return Response(
                {"error": "This asset has already been successfully appraised."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        asset.appraise_status = AssetAppraisalStatus.APPRAISAL_SUCCESSFUL
        asset.appraisal_at = timezone.now()
        asset.save()

        appraiser = request.user.appraiser_profile
        appraiser.status = AppraiserStatus.ACTIVE
        appraiser.save()

        return Response(
            {"message": "Appraisal completed successfully."},
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated], url_path="complete-appraisal-failed"
    )
    def complete_appraisal_failed(self, request, pk=None):
        asset = self.get_object()
        if not (request.user.appraiser_profile == asset.appraiser):
            return Response(
                {"error": "You are not the assigned appraiser for this asset."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if asset.appraise_status == AssetAppraisalStatus.APPRAISAL_FAILED:
            return Response(
                {"error": "This asset has already been marked as appraisal failed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        asset.appraise_status = AssetAppraisalStatus.APPRAISAL_FAILED
        asset.appraised_value = None
        asset.appraisal_at = timezone.now()
        asset.save()

        appraiser = request.user.appraiser_profile
        appraiser.status = AppraiserStatus.ACTIVE
        appraiser.save()

        return Response(
            {"message": "Appraisal marked as failed."},
            status=status.HTTP_200_OK,
        )


class AppraiserViewSet(viewsets.ModelViewSet):
    queryset = Appraiser.objects.all()
    serializer_class = AppraiserSerializer

    def get_permissions(self):
        if self.action in [
            "list",
            "retrieve",
            "create",
            "update",
            "partial_update",
            "destroy",
        ]:
            permission_classes = [IsStaffUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[permissions.IsAuthenticated],
        serializer_class=AssetSerializer, url_path="current-asset-assignment"
    )
    def current_asset_assignment(self, request):
        if not Appraiser.objects.filter(user=request.user).exists():
            return Response({"error": "You must be the appraiser to see asset assignment."}, status=status.HTTP_403_FORBIDDEN)

        current_asset = Asset.objects.filter(
            appraiser=request.user.appraiser_profile,
            appraise_status=AssetAppraisalStatus.UNDER_APPRAISAL,
        ).first()

        if current_asset:
            serializer = AssetSerializer(current_asset)
            return Response(serializer.data)
        else:
            return Response(
                {"message": "You have no current assignments."},
                status=status.HTTP_200_OK,
            )


class AssetMediaViewSet(viewsets.ModelViewSet):
    queryset = AssetMedia.objects.all()
    serializer_class = AssetMediaSerializer
    permission_classes = [AssetMediaPermission]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["media_type"]
    ordering_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return AssetMedia.objects.none()
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return AssetMedia.objects.all()
        return AssetMedia.objects.filter(asset__seller=user)
    
    def perform_create(self, serializer):
        asset = serializer.validated_data.get("asset")
        if not Asset.objects.filter(id=asset.id).exists():
            raise ValidationError("The asset does not exist.")
        
        if (
            asset.seller != self.request.user
            and not self.request.user.is_staff
            and not self.request.user.is_superuser
        ):
            raise PermissionDenied(
                "You do not have permission to add media to this asset."
            )
        
        if asset.appraise_status != AssetAppraisalStatus.NOT_APPRAISED:
            if not self.request.user.is_staff and not self.request.user.is_superuser:
                raise PermissionDenied(
                    "You do not have permission to add media to an asset that is not yet appraised."
                )

        media_type = serializer.validated_data.get("media_type")
        
        existing_media_count = AssetMedia.objects.filter(
            asset=asset,
            media_type=media_type
        ).count()

        if media_type == AssetMediaType.IMAGE:
            if existing_media_count > 20:
                raise ValidationError("This asset already has the maximum number of images (20).")
        elif media_type == AssetMediaType.VIDEO:
            if existing_media_count > 10:
                raise ValidationError("This asset already has the maximum number of videos (10).")
        elif media_type == AssetMediaType.DOCUMENT:
            pass
        else:
            raise ValidationError(f"Invalid media type: {media_type}")

        serializer.save()
