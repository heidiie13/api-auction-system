from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.routers import DefaultRouter
from .views import (signup, change_password, request_reset_password, reset_password, login, logout, verify_email, resend_verification_email, UserViewSet, UserDetailView)

router = DefaultRouter()
router.register('users', UserViewSet, basename='user')

urlpatterns = [
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('login/', login, name='login'),
    path('logout/', logout, name='logout'),
    path('signup/', signup, name='signup'),
    path('verify-email/<str:uidb64>/<str:token>/',verify_email, name='verify_email'),
    path('resend-verification-email/', resend_verification_email,name='resend_verification_email'),
    path('request-reset-password/', request_reset_password, name='request_reset_password'),
    path('reset-password/<uidb64>/<token>/', reset_password, name='reset_password'),
    path('users/me/change-password/', change_password, name='change-password'),
    path('users/me/', UserDetailView.as_view(), name='user_detail'),
    path('', include(router.urls)),
]
