from django.contrib import admin
from django.urls import path, include

admin.site.site_header = "MDH Stoma Care Clinic — Administration"
admin.site.site_title = "MDH Stoma Care Clinic"
admin.site.index_title = "Clinic data administration"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("clinic.api_urls")),
    path("", include("clinic.urls")),
]
