from rest_framework import serializers

from . import models


class PatientSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = models.Patient
        fields = "__all__"

    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.surname or ''}".strip()


class AppointmentSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()

    class Meta:
        model = models.Appointment
        fields = "__all__"

    def get_patient_name(self, obj):
        return str(obj.patient) if obj.patient_id else None


class EpisodeStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.EpisodeStep
        fields = "__all__"


class EpisodeSerializer(serializers.ModelSerializer):
    steps = EpisodeStepSerializer(many=True, read_only=True)

    class Meta:
        model = models.Episode
        fields = "__all__"


class FollowupSeenEpisodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.FollowupSeenEpisode
        fields = "__all__"


class EncounterSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()

    class Meta:
        model = models.Encounter
        fields = "__all__"

    def get_patient_name(self, obj):
        return str(obj.patient) if obj.patient_id else None


class StaffSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Staff
        fields = "__all__"


class RosterSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Roster
        fields = "__all__"


class LeaveRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.LeaveRecord
        fields = "__all__"
