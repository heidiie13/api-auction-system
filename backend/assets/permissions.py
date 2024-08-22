from rest_framework.permissions import BasePermission
from assets.enums import AssetAppraisalStatus
from users.permissions import IsStaffUser, IsAdminUser


class AssetPermission(BasePermission):
    def has_permission(self, request, view):
        if view.action in [
            "create",
            "list",
            "retrieve",
            "update",
            "partial_update",
            "destroy",
        ]:
            return request.user.is_authenticated
        return False

    def has_object_permission(self, request, view, obj):
        if view.action in ["list", "retrieve"]:
            return (
                obj.seller == request.user
                or IsStaffUser().has_permission(request, view)
                or IsAdminUser().has_permission(request, view)
            )
        elif view.action in ["update", "partial_update", "destroy"]:
            if obj.appraise_status == AssetAppraisalStatus.NOT_APPRAISED:
                return obj.seller == request.user
            else:
                return IsStaffUser().has_permission(
                    request, view
                ) or IsAdminUser().has_permission(request, view)
        return False


class AssetMediaPermission(BasePermission):
    def has_permission(self, request, view):
        if view.action in [
            "create",
            "list",
            "retrieve",
            "update",
            "partial_update",
            "destroy",
        ]:
            return request.user.is_authenticated
        return False

    def has_object_permission(self, request, view, obj):
        if view.action in ["list", "retrieve"]:
            return (
                obj.asset.seller == request.user
                or request.user.is_staff
                or request.user.is_superuser
            )
        elif view.action in ["update", "partial_update", "destroy"]:
            if obj.asset.appraise_status == AssetAppraisalStatus.NOT_APPRAISED:
                return (
                    obj.asset.seller == request.user
                    or request.user.is_staff
                    or request.user.is_superuser
                )
            else:
                return request.user.is_staff or request.user.is_superuser
        return False
