from django.urls import path

from . import views

app_name = "clinic"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("ward/", views.ward, name="ward"),
    path("patients/", views.patient_list, name="patient_list"),
    path("patients/<uuid:patient_id>/", views.patient_detail, name="patient_detail"),
]
