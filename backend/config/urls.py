from django.contrib.auth import views as auth_views
from django.urls import path, include

urlpatterns = [
    # Access is direct (auto-login middleware). Anyone who lands on /login/
    # is already signed in as the shared account, so bounce them to the app.
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("api/", include("clinic.api_urls")),
    path("", include("clinic.urls")),
]
