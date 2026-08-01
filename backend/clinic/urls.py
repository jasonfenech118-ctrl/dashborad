from django.urls import path

from . import views

app_name = "clinic"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("clinic/today/", views.todays_clinic, name="todays_clinic"),
    path("ward/", views.ward, name="ward"),
    path("letters/discharge/", views.discharge_letter, name="discharge_letter"),
    path("ordering/", views.ordering_forms, name="ordering_forms"),
    path("outcomes/", views.patient_outcomes, name="patient_outcomes"),
    path("registers/", views.registers, name="registers"),
    path("correspondence/", views.correspondence, name="correspondence"),
    path("reminders/", views.reminders, name="reminders"),
    path("more/", views.more_tools, name="more_tools"),
    path("patients/add/", views.add_patient, name="add_patient"),
    path("patients/", views.patient_list, name="patient_list"),
    path("patients/<uuid:patient_id>/", views.patient_detail, name="patient_detail"),
]
