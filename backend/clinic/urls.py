from django.urls import path

from . import views

app_name = "clinic"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("ward/", views.ward, name="ward"),
    path("letters/discharge/", views.discharge_letter, name="discharge_letter"),
    path("reports/", views.reports, name="reports"),
    path("ordering/", views.ordering_forms, name="ordering_forms"),
    path("ordering/esrf/", views.esrf_form, name="esrf_form"),
    path("documents/", views.clinic_documents, name="clinic_documents"),
    path("more/", views.more_tools, name="more_tools"),
    path("patients/add/", views.add_patient, name="add_patient"),
    path("patients/", views.patient_list, name="patient_list"),
    path("patients/<uuid:patient_id>/", views.patient_detail, name="patient_detail"),
]
