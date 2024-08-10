from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.urls import reverse
from django.conf import settings

class AccountActivationTokenGenerator(PasswordResetTokenGenerator):
    def __init__(self, timeout=300):
        super().__init__()
        self.timeout = timeout

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{timestamp}{user.is_active}"

    def check_token(self, user, token):
        if not (user and token):
            return False

        try:
            ts_b36, _ = token.split("-")
            ts = int(ts_b36, 36)
        except ValueError:
            return False

        if (self._num_seconds(self._now()) - ts) > self.timeout:
            return False

        return super().check_token(user, token)

account_activation_token = AccountActivationTokenGenerator()

class PasswordResetTokenGeneratorCustom(PasswordResetTokenGenerator):
    def __init__(self, timeout=300):
        super().__init__()
        self.timeout = timeout


    def check_token(self, user, token):
        if not (user and token):
            return False

        try:
            ts_b36, _ = token.split("-")
            ts = int(ts_b36, 36)
        except ValueError:
            return False

        if (self._num_seconds(self._now()) - ts) > self.timeout:
            return False

        return super().check_token(user, token)

password_reset_token = PasswordResetTokenGeneratorCustom()


def send_verification_email(user, request):
    token = account_activation_token.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    verification_link = request.build_absolute_uri(
        reverse('verify_email', kwargs={'uidb64': uid, 'token': token})
    )

    subject = '[American Auction] Verify Account'
    message = f'Hi, {user.email} \nClick the link below to verify your email address:\n\n{verification_link}\nThis link will expire in 5 minutes'
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])