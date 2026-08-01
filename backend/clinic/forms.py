"""Forms for the clinic app."""

from django import forms

from . import models


SEX_CHOICES = [
    ("", "— Select —"),
    ("Male", "Male"),
    ("Female", "Female"),
    ("Other", "Other"),
]

# Data-protection / consent selection
DPA_CHOICES = [
    ("", "— Select —"),
    ("Signed", "Consent form signed"),
    ("Verbal", "Verbal consent given"),
    ("Declined", "Consent declined"),
    ("Pending", "Pending"),
]

FOLLOWUP_STATUS_CHOICES = [
    ("active", "Active"),
    ("inpatient", "Inpatient"),
    ("reversed", "Reversed"),
    ("deceased", "Deceased"),
    ("relocated_gozo", "Discharged to Gozo"),
    ("relocated_overseas", "Relocated Overseas"),
]


class _DateInput(forms.DateInput):
    input_type = "date"


class PatientForm(forms.ModelForm):
    """Create a new patient record with demographics, surgery, clinical
    findings, medical/social history and a data-protection selection."""

    sex = forms.ChoiceField(choices=SEX_CHOICES, required=False)
    dpa_status = forms.ChoiceField(
        choices=DPA_CHOICES, required=False, label="Data protection consent"
    )
    followup_status = forms.ChoiceField(
        choices=FOLLOWUP_STATUS_CHOICES, required=False, initial="active",
        label="Follow-up status",
    )

    class Meta:
        model = models.Patient
        fields = [
            # demographics
            "first_name", "surname", "id_card", "dob", "sex",
            "phone_number", "locality",
            # surgery / admission
            "surgery_date", "planned_surgery_date", "surgery_type",
            "operation_performed", "consultant", "admission_route",
            "inpatient_type",
            # clinical findings
            "findings", "stoma_type_summary",
            # medical history
            "past_medical_history", "past_surgical_history", "drug_history",
            "medication_additional_notes",
            # social history
            "social_history",
            # data protection
            "dpa_status",
            # follow-up
            "followup_owner", "followup_status",
        ]
        widgets = {
            "dob": _DateInput(),
            "surgery_date": _DateInput(),
            "planned_surgery_date": _DateInput(),
            "findings": forms.Textarea(attrs={"rows": 3}),
            "stoma_type_summary": forms.Textarea(attrs={"rows": 2}),
            "operation_performed": forms.Textarea(attrs={"rows": 2}),
            "past_medical_history": forms.Textarea(attrs={"rows": 3}),
            "past_surgical_history": forms.Textarea(attrs={"rows": 3}),
            "drug_history": forms.Textarea(attrs={"rows": 3}),
            "medication_additional_notes": forms.Textarea(attrs={"rows": 2}),
            "social_history": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "id_card": "ID card",
            "dob": "Date of birth",
            "locality": "Locality",
            "planned_surgery_date": "Planned surgery date",
            "surgery_type": "Surgery type",
            "operation_performed": "Operation performed",
            "admission_route": "Admission route",
            "inpatient_type": "Inpatient type",
            "stoma_type_summary": "Stoma type",
            "past_medical_history": "Past medical history",
            "past_surgical_history": "Past surgical history",
            "drug_history": "Drug history",
            "medication_additional_notes": "Medication notes",
            "social_history": "Social history",
            "followup_owner": "Follow-up owner",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # First name and surname are the minimum needed to identify a patient.
        self.fields["first_name"].required = True
        self.fields["surname"].required = True
        # A sensible default for a newly admitted patient.
        if not self.is_bound:
            self.fields["followup_status"].initial = "active"
        # Add a shared CSS hook to every widget for styling.
        for name, field in self.fields.items():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (css + " f-input").strip()
