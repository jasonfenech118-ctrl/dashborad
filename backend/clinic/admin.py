from django.contrib import admin

from . import models


@admin.register(models.Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("surname", "first_name", "id_card", "followup_status",
                    "followup_owner", "admission_route", "surgery_date")
    list_filter = ("followup_status", "admission_route", "followup_owner", "sex")
    search_fields = ("first_name", "surname", "id_card", "phone_number", "locality")
    ordering = ("surname", "first_name")
    date_hierarchy = "surgery_date"


@admin.register(models.Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("appt_date", "appt_slot", "patient", "status",
                    "assigned_to", "bank_staff")
    list_filter = ("status", "appt_date")
    search_fields = ("patient__first_name", "patient__surname", "patient__id_card")
    date_hierarchy = "appt_date"
    autocomplete_fields = ("patient",)
    raw_id_fields = ("assigned_to", "bank_staff")


class EpisodeStepInline(admin.TabularInline):
    model = models.EpisodeStep
    extra = 0
    fields = ("step_no", "step_key", "status", "completed_by", "completed_at")
    readonly_fields = ()
    ordering = ("step_no",)


@admin.register(models.Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = ("patient", "pathway_type", "status", "surgery_date", "created_at")
    list_filter = ("pathway_type", "status")
    search_fields = ("patient__first_name", "patient__surname")
    inlines = [EpisodeStepInline]
    autocomplete_fields = ("patient",)


@admin.register(models.EpisodeStep)
class EpisodeStepAdmin(admin.ModelAdmin):
    list_display = ("episode", "step_no", "step_key", "status", "completed_at")
    list_filter = ("status", "step_key")


@admin.register(models.FollowupSeenEpisode)
class FollowupSeenEpisodeAdmin(admin.ModelAdmin):
    list_display = ("full_episode_code", "patient", "review_date",
                    "stoma_colour", "followup_status", "recorded_by_name")
    list_filter = ("followup_status", "stoma_colour", "review_date")
    search_fields = ("patient_name", "patient_id_card", "full_episode_code")
    date_hierarchy = "review_date"


@admin.register(models.Encounter)
class EncounterAdmin(admin.ModelAdmin):
    list_display = ("encounter_date", "encounter_type", "patient", "recorded_by")
    list_filter = ("encounter_type", "encounter_date")
    search_fields = ("patient__first_name", "patient__surname", "summary")
    date_hierarchy = "encounter_date"


@admin.register(models.Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ("full_name", "role")
    search_fields = ("full_name",)


@admin.register(models.BankStaff)
class BankStaffAdmin(admin.ModelAdmin):
    list_display = ("full_name", "role")
    search_fields = ("full_name",)


@admin.register(models.Roster)
class RosterAdmin(admin.ModelAdmin):
    list_display = ("roster_date", "staff", "status")
    list_filter = ("status", "roster_date")
    search_fields = ("staff__full_name",)
    date_hierarchy = "roster_date"


@admin.register(models.LeaveRecord)
class LeaveRecordAdmin(admin.ModelAdmin):
    list_display = ("staff", "leave_type", "start_date", "end_date", "total_days")
    list_filter = ("leave_type",)
    search_fields = ("staff__full_name",)
    date_hierarchy = "start_date"


@admin.register(models.BankStaffAssignment)
class BankStaffAssignmentAdmin(admin.ModelAdmin):
    list_display = ("work_date", "bank_staff", "shift_start", "shift_end")
    list_filter = ("work_date",)
    search_fields = ("bank_staff__full_name",)
    date_hierarchy = "work_date"


@admin.register(models.PublicHoliday)
class PublicHolidayAdmin(admin.ModelAdmin):
    list_display = ("holiday_date", "name")
    date_hierarchy = "holiday_date"
