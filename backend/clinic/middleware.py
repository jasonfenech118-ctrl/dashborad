"""Direct-access middleware.

Signs every visitor in automatically as one shared account so the clinic app
never shows a login page. The Django admin is unaffected: the shared account
is a normal (non-staff) user, so /admin/ still requires a real login.
"""

from django.conf import settings
from django.contrib.auth import get_user_model, login

SHARED_USERNAME = getattr(settings, "SHARED_USERNAME", "stoma")


class AutoLoginMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            try:
                User = get_user_model()
                user, created = User.objects.get_or_create(
                    username=SHARED_USERNAME,
                    defaults={"first_name": "Stoma", "last_name": "Care", "is_active": True},
                )
                if created:
                    user.set_unusable_password()
                    user.save(update_fields=["password"])
                # login() needs a backend when we didn't call authenticate().
                user.backend = "django.contrib.auth.backends.ModelBackend"
                login(request, user)
            except Exception:
                # Database not reachable — let the request continue unauthenticated
                # (a protected view will then fall back to the normal login page).
                pass
        return self.get_response(request)
