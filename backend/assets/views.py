from django.forms import ValidationError
from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
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
    AssetSerializer,
    AssetAppraisalSerializer,
)
from .enums import AssetStatus, AppraiserStatus, AssetAppraisalStatus
from users.permissions import IsAdminUser, IsStaffUser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import PermissionDenied


class AssetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class AssetViewSet(viewsets.ModelViewSet):
    queryset = Asset.objects.all()
    serializer_class = AssetSerializer
    permission_classes = [AssetPermission]
    pagination_class = AssetPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["category", "status"]
    ordering_fields = ["created_at", "name", "updated_at"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.request.user.is_staff or self.request.user.is_superuser:
            return AdminAssetSerializer
        return AssetSerializer

    def get_queryset(self):
        if self.request.user.is_staff or self.request.user.is_superuser:
            return Asset.objects.all()
        return Asset.objects.filter(seller=self.request.user)

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)

    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
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

        if asset.appraiser:
            return Response(
                {"error": "This asset already has an appraiser assigned."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        appraiser = Appraiser.objects.filter(status=AppraiserStatus.ACTIVE).first()
        if not appraiser:
            return Response(
                {"error": "No inactive appraiser available."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        asset.appraise_status = AssetAppraisalStatus.UNDER_APPRAISAL
        asset.appraiser = appraiser
        asset.save()

        appraiser.status = AppraiserStatus.INACTIVE
        appraiser.save()

        return Response(
            {"message": "Asset registered for auction and appraiser assigned."},
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["patch"],
        permission_classes=[permissions.IsAuthenticated],
        serializer_class=AssetAppraisalSerializer,
    )
    def update_appraisal(self, request, pk=None):
        asset = self.get_object()
        if not (request.user.appraiser_profile == asset.appraiser):
            return Response(
                {"error": "You are not the assigned appraiser for this asset."},
                status=status.HTTP_403_FORBIDDEN,
            )

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
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def complete_appraisal_successful(self, request, pk=None):
        asset = self.get_object()
        if not (request.user.appraiser_profile == asset.appraiser):
            return Response(
                {"error": "You are not the assigned appraiser for this asset."},
                status=status.HTTP_403_FORBIDDEN,
            )

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
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
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
    """ViewSet for managing appraisers."""

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
            permission_classes = [IsStaffUser | IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]


    @action(
        detail=True,
        methods=["get"],
        permission_classes=[permissions.IsAuthenticated],
        serializer_class=AssetSerializer,
    )
    def current_asset_assignment(self, request, pk=None):
        appraiser = self.get_object()
        if request.user.appraiser_profile != appraiser:
            return Response(
                {"error": "You can only view your own assignments."},
                status=status.HTTP_403_FORBIDDEN,
            )

        current_asset = Asset.objects.filter(
            appraiser=appraiser,
            appraise_status=AssetAppraisalStatus.NOT_APPRAISED,
        ).first()

        if current_asset:
            serializer = AssetSerializer(current_asset)
            return Response(serializer.data)
        else:
            return Response(
                {"message": "You have no current assignments."},
                status=status.HTTP_200_OK,
            )


class AssetMediaPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class AssetMediaViewSet(viewsets.ModelViewSet):
    queryset = AssetMedia.objects.all()
    serializer_class = AssetMediaSerializer
    permission_classes = [AssetMediaPermission]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["media_type"]
    ordering_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]
    pagination_class = AssetMediaPagination

    def get_queryset(self):
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
        serializer.save()


    def create(self, request, *args, **kwargs):
        # Ensure the file is provided in the request
        if "file" not in request.FILES:
            return Response(
                {"error": "No file provided."}, status=status.HTTP_400_BAD_REQUEST
            )

        # Pass the request context to the serializer
        serializer = self.get_serializer(data=request.data, context={"request": request})
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(
                serializer.data, status=status.HTTP_201_CREATED, headers=headers
            )
        except ValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except PermissionDenied as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_403_FORBIDDEN,
            )
        except Exception as e:
            return Response(
                {"error": "An unknown error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
