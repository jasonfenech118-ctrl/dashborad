"""
Django models for the MDH Stoma Care Clinic.

These map onto the EXISTING Supabase Postgres tables (managed = False), so
Django reads and writes the live data with no migration and no data loss.
When the app is fully migrated off Supabase, flip `managed = True` in the
Meta classes and let Django own the schema.
"""

import uuid

from django.db import models


class UUIDModel(models.Model):
    """Base with a Supabase-style uuid primary key generated client-side."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


# ---------------------------------------------------------------- staffing


class Staff(UUIDModel):
    full_name = models.CharField(max_length=200)
    role = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "staff"
        verbose_name_plural = "Staff"

    def __str__(self):
        return self.full_name


class BankStaff(UUIDModel):
    full_name = models.CharField(max_length=200)
    role = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "bank_staff"
        verbose_name_plural = "Bank staff"

    def __str__(self):
        return self.full_name


class PublicHoliday(UUIDModel):
    holiday_date = models.DateField()
    name = models.CharField(max_length=200)

    class Meta:
        managed = False
        db_table = "public_holidays"

    def __str__(self):
        return f"{self.holiday_date} — {self.name}"


# ---------------------------------------------------------------- patients


class Patient(UUIDModel):
    id_card = models.CharField(max_length=50, blank=True, null=True)
    first_name = models.CharField(max_length=120, blank=True, null=True)
    surname = models.CharField(max_length=120, blank=True, null=True)
    phone_number = models.CharField(max_length=50, blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    locality = models.CharField(max_length=120, blank=True, null=True)
    sex = models.CharField(max_length=20, blank=True, null=True)

    # surgery / admission
    surgery_date = models.DateField(blank=True, null=True)
    planned_surgery_date = models.DateField(blank=True, null=True)
    inpatient_type = models.CharField(max_length=60, blank=True, null=True)
    admission_route = models.CharField(max_length=80, blank=True, null=True)
    operation_performed = models.TextField(blank=True, null=True)
    surgery_event_operation_performed = models.TextField(blank=True, null=True)
    surgery_type = models.CharField(max_length=80, blank=True, null=True)
    consultant = models.CharField(max_length=120, blank=True, null=True)

    # clinical
    findings = models.TextField(blank=True, null=True)
    stoma_type_summary = models.TextField(blank=True, null=True)
    past_medical_history = models.TextField(blank=True, null=True)
    past_surgical_history = models.TextField(blank=True, null=True)
    drug_history = models.TextField(blank=True, null=True)
    medication_history = models.JSONField(blank=True, null=True)
    medication_history_other = models.TextField(blank=True, null=True)
    medication_additional_notes = models.TextField(blank=True, null=True)
    social_history = models.TextField(blank=True, null=True)
    dpa_status = models.CharField(max_length=60, blank=True, null=True)
    clinical_complications = models.TextField(blank=True, null=True)

    # follow-up
    followup_owner = models.CharField(max_length=120, blank=True, null=True)
    followup_due_month = models.IntegerField(blank=True, null=True)
    followup_year = models.IntegerField(blank=True, null=True)
    followup_status = models.CharField(max_length=40, blank=True, null=True)
    followup_type = models.CharField(max_length=40, blank=True, null=True)
    next_followup_mirror = models.DateField(blank=True, null=True)

    # outcomes / registry
    reversal_date = models.DateField(blank=True, null=True)
    rip_date = models.DateField(blank=True, null=True)
    discharged_date = models.DateField(blank=True, null=True)
    last_outcome_date = models.DateField(blank=True, null=True)
    active_registry = models.BooleanField(blank=True, null=True)
    patient_status_raw = models.CharField(max_length=80, blank=True, null=True)
    stoma_days = models.IntegerField(blank=True, null=True)
    age_at_death = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "patients"

    def __str__(self):
        name = f"{self.first_name or ''} {self.surname or ''}".strip()
        return name or (self.id_card or str(self.id))


# ---------------------------------------------------------------- appointments


class Appointment(UUIDModel):
    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, db_column="patient_id",
        blank=True, null=True, related_name="appointments",
    )
    appt_date = models.DateField(blank=True, null=True)
    appt_slot = models.CharField(max_length=20, blank=True, null=True)
    assigned_to = models.ForeignKey(
        Staff, on_delete=models.SET_NULL, db_column="assigned_to",
        blank=True, null=True, related_name="appointments",
    )
    bank_staff = models.ForeignKey(
        BankStaff, on_delete=models.SET_NULL, db_column="bank_staff_id",
        blank=True, null=True, related_name="appointments",
    )
    status = models.CharField(max_length=30, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    outcome_recorded_at = models.DateTimeField(blank=True, null=True)
    outcome_recorded_by_email = models.CharField(max_length=200, blank=True, null=True)
    outcome_recorded_by_name = models.CharField(max_length=200, blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    cancelled_by_email = models.CharField(max_length=200, blank=True, null=True)
    cancelled_by_name = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "appointments"

    def __str__(self):
        return f"{self.appt_date} {self.appt_slot or ''} — {self.patient}"


# ---------------------------------------------------------------- episodes


class Episode(UUIDModel):
    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, db_column="patient_id",
        blank=True, null=True, related_name="episodes",
    )
    pathway_type = models.CharField(max_length=40, blank=True, null=True)
    status = models.CharField(max_length=30, blank=True, null=True)
    created_by = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    surgery_date = models.DateField(blank=True, null=True)
    post_op_start = models.DateField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "episodes"

    def __str__(self):
        return f"{self.pathway_type or 'episode'} — {self.patient}"


class EpisodeStep(UUIDModel):
    episode = models.ForeignKey(
        Episode, on_delete=models.CASCADE, db_column="episode_id",
        blank=True, null=True, related_name="steps",
    )
    step_no = models.IntegerField(blank=True, null=True)
    step_key = models.CharField(max_length=60, blank=True, null=True)
    status = models.CharField(max_length=30, blank=True, null=True)
    data = models.JSONField(blank=True, null=True)
    completed_by = models.CharField(max_length=200, blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "episode_steps"
        ordering = ["step_no"]

    def __str__(self):
        return f"Step {self.step_no} ({self.step_key}) — {self.status}"


# ------------------------------------------------------ follow-up seen episodes


class FollowupSeenEpisode(UUIDModel):
    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, db_column="patient_id",
        blank=True, null=True, related_name="followup_seen_episodes",
    )
    appointment = models.ForeignKey(
        Appointment, on_delete=models.SET_NULL, db_column="appointment_id",
        blank=True, null=True, related_name="followup_seen_episodes",
    )
    episode_code = models.CharField(max_length=80, blank=True, null=True)
    base_episode_code = models.CharField(max_length=80, blank=True, null=True)
    version_number = models.IntegerField(blank=True, null=True)
    full_episode_code = models.CharField(max_length=100, blank=True, null=True)
    review_date = models.DateField(blank=True, null=True)
    patient_id_card = models.CharField(max_length=50, blank=True, null=True)
    patient_name = models.CharField(max_length=200, blank=True, null=True)
    phone_number = models.CharField(max_length=50, blank=True, null=True)
    stoma_colour = models.CharField(max_length=80, blank=True, null=True)
    stoma_colour_other = models.CharField(max_length=200, blank=True, null=True)
    stoma_function = models.CharField(max_length=80, blank=True, null=True)
    stoma_function_other = models.CharField(max_length=200, blank=True, null=True)
    peristomal_skin = models.CharField(max_length=80, blank=True, null=True)
    peristomal_skin_other = models.CharField(max_length=200, blank=True, null=True)
    appliances_used = models.JSONField(blank=True, null=True)
    accessories_used = models.JSONField(blank=True, null=True)
    followup_owner = models.CharField(max_length=120, blank=True, null=True)
    followup_due_month = models.IntegerField(blank=True, null=True)
    followup_year = models.IntegerField(blank=True, null=True)
    followup_status = models.CharField(max_length=40, blank=True, null=True)
    nursing_report = models.TextField(blank=True, null=True)
    episode_data = models.JSONField(blank=True, null=True)
    changed_fields = models.JSONField(blank=True, null=True)
    edited_from_episode = models.ForeignKey(
        "self", on_delete=models.SET_NULL, db_column="edited_from_episode_id",
        blank=True, null=True, related_name="revisions",
    )
    recorded_by_email = models.CharField(max_length=200, blank=True, null=True)
    recorded_by_name = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "followup_seen_episodes"

    def __str__(self):
        return self.full_episode_code or self.episode_code or str(self.id)


# ---------------------------------------------------------------- encounters


class Encounter(UUIDModel):
    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, db_column="patient_id",
        related_name="encounters",
    )
    appointment = models.ForeignKey(
        Appointment, on_delete=models.SET_NULL, db_column="appointment_id",
        blank=True, null=True, related_name="encounters",
    )
    encounter_type = models.CharField(max_length=60)
    encounter_date = models.DateField()
    encounter_time = models.CharField(max_length=20, blank=True, null=True)
    recorded_by = models.CharField(max_length=200, blank=True, null=True)
    data = models.JSONField(default=dict, blank=True)
    summary = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "encounters"
        ordering = ["-encounter_date"]

    def __str__(self):
        return f"{self.encounter_type} — {self.encounter_date} — {self.patient}"


# ---------------------------------------------------------------- roster / leave


class Roster(UUIDModel):
    staff = models.ForeignKey(
        Staff, on_delete=models.CASCADE, db_column="staff_id",
        blank=True, null=True, related_name="roster_entries",
    )
    roster_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=40, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "roster"

    def __str__(self):
        return f"{self.staff} — {self.roster_date} — {self.status}"


class LeaveRecord(UUIDModel):
    staff = models.ForeignKey(
        Staff, on_delete=models.CASCADE, db_column="staff_id",
        blank=True, null=True, related_name="leave_records",
    )
    leave_type = models.CharField(max_length=40, blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    total_days = models.IntegerField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "leave_records"

    def __str__(self):
        return f"{self.staff} — {self.leave_type} ({self.start_date})"


class BankStaffAssignment(UUIDModel):
    bank_staff = models.ForeignKey(
        BankStaff, on_delete=models.CASCADE, db_column="bank_staff_id",
        blank=True, null=True, related_name="assignments",
    )
    work_date = models.DateField(blank=True, null=True)
    shift_start = models.CharField(max_length=20, blank=True, null=True)
    shift_end = models.CharField(max_length=20, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "bank_staff_assignments"

    def __str__(self):
        return f"{self.bank_staff} — {self.work_date}"


# ------------------------------------------------ ordering / clinic documents


class OrderingDocument(UUIDModel):
    """An ordering form that has been submitted (and emailed) to Logistics.

    Unlike the models above this table is owned by Django (managed = True), so
    it is created by a normal migration. It is the backing store for the
    Clinic Documents archive: every requisition sent from the app is saved
    here so the team keeps a permanent, searchable record.
    """

    STATUS_SENT = "sent"
    STATUS_SAVED = "saved"  # saved but email not delivered (not configured / failed)
    STATUS_CHOICES = [
        (STATUS_SENT, "Sent"),
        (STATUS_SAVED, "Saved (not emailed)"),
    ]

    reference = models.CharField(max_length=60, unique=True)
    form_type = models.CharField(max_length=40, default="ESRF STO-01")
    section_ward = models.CharField(max_length=120, default="Stoma Care")
    cost_centre = models.CharField(max_length=40, default="STO-01")
    ext_no = models.CharField(max_length=40, blank=True, null=True)
    delivery_period = models.CharField(max_length=120, blank=True, null=True)

    # The line items: list of {code, description, app, ef, reason}.
    items = models.JSONField(default=list, blank=True)

    requested_by_name = models.CharField(max_length=200, blank=True, null=True)
    requested_by_username = models.CharField(max_length=200, blank=True, null=True)
    form_date = models.DateField(blank=True, null=True)

    recipient_email = models.CharField(max_length=200, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SAVED)
    sent_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        db_table = "ordering_documents"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} — {self.section_ward}"

    @property
    def item_count(self):
        """Number of line items that actually carry a code or description."""
        return sum(
            1 for it in (self.items or [])
            if (it.get("code") or it.get("description"))
        )


class CarePathway(UUIDModel):
    """A patient's stoma/fistula care episode, from referral to follow-up.

    One pathway = one episode (e.g. an admission). It carries many
    PathwayEvents (the day-by-day reviews, education and supplies given).
    Managed by Django, so it does not disturb the Supabase-owned tables.
    """

    ELECTIVE = "elective"
    EMERGENCY = "emergency"
    OLD_CASE = "old_case"
    FISTULA = "fistula"
    TYPE_CHOICES = [
        (ELECTIVE, "Elective"),
        (EMERGENCY, "Emergency"),
        (OLD_CASE, "Old case (operated elsewhere)"),
        (FISTULA, "Fistula"),
    ]

    # Stages a pathway moves through.
    SITING_SCHEDULED = "siting_scheduled"
    AWAITING_SURGERY = "awaiting_surgery"
    INPATIENT = "inpatient"
    OUTPATIENT = "outpatient"
    DISCHARGED = "discharged"
    FOLLOWUP = "followup"
    CLOSED = "closed"
    STATUS_CHOICES = [
        (SITING_SCHEDULED, "Siting scheduled"),
        (AWAITING_SURGERY, "Awaiting surgery"),
        (INPATIENT, "Inpatient — under review"),
        (OUTPATIENT, "Outpatient"),
        (DISCHARGED, "Discharged"),
        (FOLLOWUP, "Follow-up (old stoma)"),
        (CLOSED, "Closed"),
    ]

    INPATIENT_SETTING = "inpatient"
    OUTPATIENT_SETTING = "outpatient"
    SETTING_CHOICES = [
        (INPATIENT_SETTING, "Inpatient"),
        (OUTPATIENT_SETTING, "Outpatient appointment"),
    ]

    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, db_constraint=False,
        related_name="care_pathways",
    )
    pathway_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)

    # Old case: where the stoma was formed, and how we see them.
    referral_source = models.CharField(max_length=200, blank=True, null=True)
    care_setting = models.CharField(
        max_length=20, choices=SETTING_CHOICES, blank=True, null=True,
    )

    # Elective: the stoma siting session (reschedulable).
    siting_scheduled_date = models.DateField(blank=True, null=True)
    siting_done_date = models.DateField(blank=True, null=True)
    siting_chart = models.JSONField(default=dict, blank=True)

    # Surgery.
    surgery_date = models.DateField(blank=True, null=True)
    stoma_type = models.CharField(max_length=120, blank=True, null=True)
    operation = models.CharField(max_length=200, blank=True, null=True)

    # Post-operative course.
    first_review_date = models.DateField(blank=True, null=True)
    discharge_date = models.DateField(blank=True, null=True)

    notes = models.TextField(blank=True, null=True)
    created_by_username = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = True
        db_table = "care_pathways"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.get_pathway_type_display()} — {self.patient}"

    # -- derived helpers -------------------------------------------------
    @property
    def needs_siting(self):
        """Only elective patients get a planned stoma siting session."""
        return self.pathway_type == self.ELECTIVE

    @property
    def expects_followup(self):
        """Fistulas are rarely followed up after discharge."""
        return self.pathway_type != self.FISTULA

    @property
    def first_review_delay_days(self):
        """Days between surgery and the first post-op review (None if n/a)."""
        if not self.surgery_date or not self.first_review_date:
            return None
        return (self.first_review_date - self.surgery_date).days

    @property
    def first_review_was_late(self):
        """True when the first post-op review wasn't day 1 — flagged so
        delayed reviews are visible rather than hidden."""
        d = self.first_review_delay_days
        return d is not None and d > 1

    @property
    def is_active(self):
        return self.status not in {self.CLOSED}


class PathwayEvent(UUIDModel):
    """A single event within a pathway — usually a daily post-op review."""

    SITING = "siting"
    SURGERY = "surgery"
    POST_OP_REVIEW = "post_op_review"
    REVIEW = "review"
    DISCHARGE = "discharge"
    FOLLOWUP = "followup"
    NOTE = "note"
    TYPE_CHOICES = [
        (SITING, "Stoma siting session"),
        (SURGERY, "Surgery"),
        (POST_OP_REVIEW, "Post-operative review"),
        (REVIEW, "Review"),
        (DISCHARGE, "Discharge"),
        (FOLLOWUP, "Follow-up review"),
        (NOTE, "Note"),
    ]

    pathway = models.ForeignKey(
        CarePathway, on_delete=models.CASCADE, related_name="events",
    )
    event_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=REVIEW)
    event_date = models.DateField()
    day_number = models.IntegerField(blank=True, null=True)  # post-op day
    summary = models.CharField(max_length=250, blank=True, null=True)
    education_given = models.BooleanField(default=False)
    supplies_given = models.BooleanField(default=False)
    notes = models.TextField(blank=True, null=True)
    data = models.JSONField(default=dict, blank=True)
    recorded_by = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        db_table = "pathway_events"
        ordering = ["-event_date", "-created_at"]

    def __str__(self):
        return f"{self.get_event_type_display()} — {self.event_date}"


class FollowUpAppointment(UUIDModel):
    """A planned follow-up / outpatient appointment for a pathway."""

    SCHEDULED = "scheduled"
    ATTENDED = "attended"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"
    DNA = "dna"
    STATUS_CHOICES = [
        (SCHEDULED, "Scheduled"),
        (ATTENDED, "Attended"),
        (POSTPONED, "Postponed"),
        (CANCELLED, "Cancelled"),
        (DNA, "Did not attend"),
    ]

    pathway = models.ForeignKey(
        CarePathway, on_delete=models.CASCADE, related_name="followup_appointments",
        blank=True, null=True,
    )
    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, db_constraint=False,
        related_name="followup_appointments_new",
    )
    appt_date = models.DateField()
    appt_time = models.CharField(max_length=20, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=SCHEDULED)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = True
        db_table = "followup_appointments"
        ordering = ["appt_date", "appt_time"]

    def __str__(self):
        return f"{self.appt_date} — {self.patient}"


class TenderEvaluation(UUIDModel):
    """A CPSU tender evaluation the user can open, work on and close.

    Managed by Django (migration-created). The full editor state — tender
    header, the bidder rows and which bidder is selected — is kept in `data`;
    a few fields are denormalised (title, status, lowest bid, bidder count) so
    the tender list renders without unpacking every record.
    """

    STATUS_OPEN = "open"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [(STATUS_OPEN, "Open"), (STATUS_CLOSED, "Closed")]

    title = models.CharField(max_length=200, default="Untitled tender")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN)
    data = models.JSONField(default=dict, blank=True)
    bidder_count = models.IntegerField(default=0)
    lowest_bid = models.FloatField(blank=True, null=True)
    lowest_bidder = models.CharField(max_length=200, blank=True, null=True)
    created_by_username = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = True
        db_table = "tender_evaluations"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.title} ({self.status})"

    @property
    def is_open(self):
        return self.status == self.STATUS_OPEN
