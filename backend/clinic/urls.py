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
    path("documents/<uuid:pk>/", views.ordering_document_detail, name="ordering_document_detail"),
    path("cpsu/", views.cpsu, name="cpsu"),
    path("cpsu/tenders/", views.cpsu_tenders, name="cpsu_tenders"),
    path("cpsu/tenders/new/", views.tender_new, name="tender_new"),
    path("cpsu/tenders/current/", views.tenders_current, name="tenders_current"),
    path("cpsu/tenders/closed/", views.tenders_closed, name="tenders_closed"),
    path("cpsu/tenders/<uuid:pk>/", views.tender_edit, name="tender_edit"),
    path("cpsu/tenders/<uuid:pk>/delete/", views.tender_delete, name="tender_delete"),
    path("more/", views.more_tools, name="more_tools"),
    path("pathways/<uuid:pk>/", views.pathway_detail, name="pathway_detail"),
    path("appointments/", views.appointments, name="appointments"),
    path("patients/add/", views.add_patient, name="add_patient"),
    path("patients/", views.patient_list, name="patient_list"),
    path("patients/<uuid:patient_id>/", views.patient_detail, name="patient_detail"),
]
