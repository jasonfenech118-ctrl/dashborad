from django.urls import path

from . import views

app_name = "clinic"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("ward/", views.ward, name="ward"),
    path("letters/discharge/", views.discharge_letter, name="discharge_letter"),
    path("letters/discharge/<uuid:patient_id>/", views.discharge_letter,
         name="discharge_letter_for"),
    path("reports/", views.reports, name="reports"),
    path("ordering/", views.ordering_forms, name="ordering_forms"),
    path("ordering/esrf/", views.esrf_form, name="esrf_form"),
    path("documents/", views.clinic_documents, name="clinic_documents"),
    path("documents/<uuid:pk>/", views.ordering_document_detail, name="ordering_document_detail"),
    path("library/", views.library, name="library"),
    path("library/file-discharge-letter/", views.file_discharge_letter,
         name="file_discharge_letter"),
    path("library/<uuid:pk>/file/", views.library_file, name="library_file"),
    path("library/<uuid:pk>/delete/", views.library_delete, name="library_delete"),
    path("cpsu/", views.cpsu, name="cpsu"),
    path("cpsu/tenders/", views.cpsu_tenders, name="cpsu_tenders"),
    path("cpsu/tenders/new/", views.tender_new, name="tender_new"),
    path("cpsu/tenders/current/", views.tenders_current, name="tenders_current"),
    path("cpsu/tenders/closed/", views.tenders_closed, name="tenders_closed"),
    path("cpsu/tenders/<uuid:pk>/", views.tender_edit, name="tender_edit"),
    path("cpsu/tenders/<uuid:pk>/delete/", views.tender_delete, name="tender_delete"),
    path("more/", views.more_tools, name="more_tools"),
    path("pathways/<uuid:pk>/", views.pathway_detail, name="pathway_detail"),
    path("pathways/<uuid:pk>/encounter/", views.encounter_new, name="encounter_new"),
    path("patients/<uuid:patient_id>/profile/", views.patient_profile, name="patient_profile"),
    path("appointments/", views.appointments, name="appointments"),
    path("patients/add/", views.add_patient, name="add_patient"),
    path("patients/", views.patient_list, name="patient_list"),
    path("patients/<uuid:patient_id>/", views.patient_detail, name="patient_detail"),
]
