from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include

admin.site.site_header = "MDH Stoma Care Clinic — Administration"
admin.site.site_title = "MDH Stoma Care Clinic"
admin.site.index_title = "Clinic data administration"

urlpatterns = [
    # App login/logout — lands on the home dashboard, not the admin site.
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("admin/", admin.site.urls),
    path("api/", include("clinic.api_urls")),
    path("", include("clinic.urls")),
]
