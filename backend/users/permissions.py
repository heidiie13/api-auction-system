from rest_framework import permissions
from .enums import UserRole

class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == UserRole.ADMIN

class IsStaffUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role in [UserRole.ADMIN, UserRole.STAFF]