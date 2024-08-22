from django.contrib import admin
from django.urls import path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework_simplejwt.authentication import JWTAuthentication

schema_view = get_schema_view(
    openapi.Info(
        title="Auction system API",
        default_version='v1',
        description="APIs for auction system",
        contact=openapi.Contact(email="american.auction.company@gmail.com"),
        license=openapi.License(name="Tung Thai")
    ),
    public=True,
    permission_classes=[permissions.AllowAny,],
)

urlpatterns = [
    path('api/', include([
        path('', include('users.urls')),
        path('', include('auctions.urls')),
        path('', include('assets.urls')),
    ])),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]