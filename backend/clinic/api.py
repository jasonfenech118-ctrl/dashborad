from rest_framework import viewsets, filters

from . import models, serializers


class PatientViewSet(viewsets.ModelViewSet):
    queryset = models.Patient.objects.all().order_by("surname", "first_name")
    serializer_class = serializers.PatientSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["first_name", "surname", "id_card", "phone_number", "locality"]
    ordering_fields = ["surname", "first_name", "surgery_date", "last_outcome_date"]

    def get_queryset(self):
        qs = super().get_queryset()
        status = self.request.query_params.get("followup_status")
        route = self.request.query_params.get("admission_route")
        if status:
            qs = qs.filter(followup_status=status)
        if route:
            qs = qs.filter(admission_route=route)
        return qs


class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = models.Appointment.objects.select_related("patient").all()
    serializer_class = serializers.AppointmentSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["patient__first_name", "patient__surname", "patient__id_card"]
    ordering_fields = ["appt_date", "appt_slot", "status"]

    def get_queryset(self):
        qs = super().get_queryset().order_by("-appt_date", "appt_slot")
        date = self.request.query_params.get("date")
        status = self.request.query_params.get("status")
        patient = self.request.query_params.get("patient")
        if date:
            qs = qs.filter(appt_date=date)
        if status:
            qs = qs.filter(status=status)
        if patient:
            qs = qs.filter(patient_id=patient)
        return qs


class EpisodeViewSet(viewsets.ModelViewSet):
    queryset = models.Episode.objects.prefetch_related("steps").all()
    serializer_class = serializers.EpisodeSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        patient = self.request.query_params.get("patient")
        return qs.filter(patient_id=patient) if patient else qs


class FollowupSeenEpisodeViewSet(viewsets.ModelViewSet):
    queryset = models.FollowupSeenEpisode.objects.all().order_by("-review_date")
    serializer_class = serializers.FollowupSeenEpisodeSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        patient = self.request.query_params.get("patient")
        return qs.filter(patient_id=patient) if patient else qs


class EncounterViewSet(viewsets.ModelViewSet):
    queryset = models.Encounter.objects.select_related("patient").all()
    serializer_class = serializers.EncounterSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["patient__first_name", "patient__surname", "summary"]
    ordering_fields = ["encounter_date", "encounter_type"]

    def get_queryset(self):
        qs = super().get_queryset()
        patient = self.request.query_params.get("patient")
        etype = self.request.query_params.get("encounter_type")
        if patient:
            qs = qs.filter(patient_id=patient)
        if etype:
            qs = qs.filter(encounter_type=etype)
        return qs


class StaffViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Staff.objects.all().order_by("full_name")
    serializer_class = serializers.StaffSerializer


class RosterViewSet(viewsets.ModelViewSet):
    queryset = models.Roster.objects.select_related("staff").all()
    serializer_class = serializers.RosterSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        date = self.request.query_params.get("date")
        return qs.filter(roster_date=date) if date else qs
