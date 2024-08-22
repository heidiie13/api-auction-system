from rest_framework.permissions import BasePermission

class IsWinner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.winner == request.user

class IsSeller(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.seller == request.user