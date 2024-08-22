from rest_framework import generics, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from django.core.mail import send_mail
from django.conf import settings
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.hashers import make_password

from .serializers import (LoginSerializer, UserSerializer, SignUpSerializer, ChangePasswordSerializer, AdminUserSerializer)
from .permissions import IsAdminUser, IsStaffUser
from .models import User
from .utils import send_verification_email, account_activation_token, password_reset_token

    
@api_view(['POST'])
@permission_classes([AllowAny])
def signup(request):
    email = request.data.get('email')
    user = User.objects.filter(email=email).first()

    if user is not None:
        if user.is_active:
            return Response({"error": "User with this email already exists and is active"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            send_verification_email(user, request)
            return Response({
                'message': 'User already registered but not verified. A new verification email has been sent.',
                'user': UserSerializer(user).data,
            }, status=status.HTTP_200_OK)

    serializer = SignUpSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    user.is_active = False
    user.save()

    send_verification_email(user, request)

    return Response({
        'message': 'User registered successfully. Please verify your email to activate your account.',
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def resend_verification_email(request):
    email = request.data.get('email')
    if not email:
        return Response({'error': 'Email address is required.'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(email=email, is_active=False)
    except User.DoesNotExist:
        return Response({"error": "No inactive user found with this email."}, status=status.HTTP_404_NOT_FOUND)

    send_verification_email(user, request)

    return Response({"message": "Verification email has been resent."}, status=status.HTTP_200_OK)
    
    
@api_view(['GET'])
@permission_classes([AllowAny])
def verify_email(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and account_activation_token.check_token(user, token):
        user.is_active = True
        user.save()
        return Response({"message": "Email verified successfully. You can now log in."}, status=status.HTTP_200_OK)
    else:
        return Response({"error": "Invalid verification link."}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def request_reset_password(request):
    email = request.data.get('email')
    if not email:
        return Response({'error': 'Email address is required.'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({"error": "User with this email does not exist."}, status=status.HTTP_404_NOT_FOUND)
    
    token = password_reset_token.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    
    reset_link = request.build_absolute_uri(
        reverse('reset_password', kwargs={'uidb64': uid, 'token': token})
    )

    subject = '[American Auction] Reset your password'
    message = f'Hi, {user.email} \nClick the link below to reset your password:\n\n{reset_link}\nThis link will expire in 5 minutes.'
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])

    return Response({"message": "A password reset link has been sent to your email."}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and password_reset_token.check_token(user, token):
        new_password = request.data.get('new_password')
        if not new_password:
            return Response({"error": "New password is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        user.password = make_password(new_password)
        user.save()

        return Response({"message": "Password has been reset successfully."}, status=status.HTTP_200_OK)
    else:
        return Response({"error": "Invalid password reset link."}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']

        user = User.objects.filter(email=email).first()

        if user is None:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return Response({"error": "This account is not active"}, status=status.HTTP_403_FORBIDDEN)

        if not user.check_password(password):
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])

        refresh = RefreshToken.for_user(user)
        return Response({
            'message': 'Login successful',
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    try:
        refresh_token = request.data.get("refresh")
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response({"message": "Successfully logged out"}, status=status.HTTP_200_OK)
    except (KeyError, TokenError):
        return Response({"error": "Invalid or missing refresh token"}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    serializer = ChangePasswordSerializer(
        data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response({"message": "Password changed successfully"}, status=status.HTTP_200_OK)

class UserDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.user.is_superuser:
            return AdminUserSerializer
        return UserSerializer

    def get_object(self):
        return self.request.user
    
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsStaffUser]
        else:
            permission_classes = [IsAdminUser]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return User.objects.none()
        if user.is_superuser:
            return User.objects.all()
        elif user.is_staff:
            return User.objects.filter(is_active=True)
        return User.objects.none()