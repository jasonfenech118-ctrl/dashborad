import datetime

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from . import models


def _safe_count(qs):
    """Return a count, or None if the table/DB isn't reachable yet."""
    try:
        return qs.count()
    except Exception:
        return None


@login_required
def dashboard(request):
    today = datetime.date.today()
    P = models.Patient.objects

    # Hero stats + register counts. Each is defensive so the page still renders
    # (showing "—") when the DB isn't connected or a table is missing.
    counts = {
        "active": _safe_count(P.filter(followup_status="active")),
        "inpatient": _safe_count(P.filter(followup_status="inpatient")),
        "reviews_today": _safe_count(
            models.Appointment.objects.filter(appt_date=today)
        ),
        "followups_due": _safe_count(
            P.filter(
                followup_status="active",
                followup_due_month=today.month,
                followup_year=today.year,
            )
        ),
        "reversed": _safe_count(P.filter(followup_status="reversed")),
        "deceased": _safe_count(P.filter(followup_status="deceased")),
        "gozo": _safe_count(P.filter(followup_status="relocated_gozo")),
        "overseas": _safe_count(P.filter(followup_status="relocated_overseas")),
    }

    def fmt(v):
        return "—" if v is None else v

    stats = {k: fmt(v) for k, v in counts.items()}
    return render(request, "clinic/dashboard.html", {"stats": stats})


@login_required
def ward(request):
    """Ward view — three-column shell mirroring the reference UI:

    left = patients at the ward, right = selected patient chart with a
    Documents records table (backed by Encounters). Defensive throughout so
    the page still renders when the DB isn't reachable.
    """
    q = (request.GET.get("q") or "").strip()

    patients = models.Patient.objects.all().order_by("surname", "first_name")
    if q:
        patients = patients.filter(
            Q(first_name__icontains=q)
            | Q(surname__icontains=q)
            | Q(id_card__icontains=q)
        )

    try:
        patients = list(patients[:200])
    except Exception:
        patients = []

    # Selected patient: ?patient=<uuid>, else the first in the list.
    selected = None
    sel_id = (request.GET.get("patient") or "").strip()
    if sel_id:
        selected = next((p for p in patients if str(p.id) == sel_id), None)
        if selected is None:
            try:
                selected = models.Patient.objects.filter(pk=sel_id).first()
            except Exception:
                selected = None
    if selected is None and patients:
        selected = patients[0]

    tab = (request.GET.get("tab") or "documents").strip()
    if tab not in {"documents", "summary", "events"}:
        tab = "documents"

    records, appointments, followups = [], [], []
    if selected is not None:
        try:
            records = list(
                models.Encounter.objects.filter(patient_id=selected.id)
                .order_by("-encounter_date")[:50]
            )
        except Exception:
            records = []
        if tab in {"summary", "events"}:
            try:
                appointments = list(
                    models.Appointment.objects.filter(patient_id=selected.id)
                    .order_by("-appt_date")[:20]
                )
            except Exception:
                appointments = []
            try:
                followups = list(
                    models.FollowupSeenEpisode.objects.filter(patient_id=selected.id)
                    .order_by("-review_date")[:20]
                )
            except Exception:
                followups = []

    return render(request, "clinic/ward.html", {
        "patients": patients,
        "ward_count": len(patients),
        "selected": selected,
        "records": records,
        "appointments": appointments,
        "followups": followups,
        "tab": tab,
        "q": q,
    })


@login_required
def discharge_letter(request):
    """Standalone Stoma discharge-letter generator.

    The template is a fully self-contained client-side tool (its own layout,
    print styles and localStorage state), so it does not extend base.html.
    """
    return render(request, "clinic/discharge_letter.html")


@login_required
def patient_list(request):
    q = (request.GET.get("q") or "").strip()
    patients = models.Patient.objects.all().order_by("surname", "first_name")
    if q:
        patients = patients.filter(
            Q(first_name__icontains=q)
            | Q(surname__icontains=q)
            | Q(id_card__icontains=q)
            | Q(phone_number__icontains=q)
            | Q(locality__icontains=q)
        )

    paginator = Paginator(patients, 40)
    page = paginator.get_page(request.GET.get("page"))

    return render(request, "clinic/patient_list.html", {
        "page": page,
        "q": q,
    })


@login_required
def deceased_list(request):
    """Register of deceased patients — read-only table.

    Defensive throughout so the page still renders (empty) when the DB
    isn't reachable or the table is missing.
    """
    q = (request.GET.get("q") or "").strip()

    patients = models.Patient.objects.filter(
        followup_status="deceased"
    ).order_by("-rip_date", "surname", "first_name")
    if q:
        patients = patients.filter(
            Q(first_name__icontains=q)
            | Q(surname__icontains=q)
            | Q(id_card__icontains=q)
        )

    try:
        patients = list(patients)
    except Exception:
        patients = []

    # Compute days from surgery to death for each row.
    for p in patients:
        p.surgery_days_till_rip = None
        if p.surgery_date and p.rip_date:
            try:
                p.surgery_days_till_rip = (p.rip_date - p.surgery_date).days
            except Exception:
                p.surgery_days_till_rip = None

    return render(request, "clinic/deceased_list.html", {
        "patients": patients,
        "count": len(patients),
        "q": q,
    })


@login_required
def patient_detail(request, patient_id):
    patient = get_object_or_404(models.Patient, pk=patient_id)
    appointments = (
        models.Appointment.objects.filter(patient_id=patient_id)
        .order_by("-appt_date", "appt_slot")
    )
    episodes = (
        models.Episode.objects.filter(patient_id=patient_id)
        .prefetch_related("steps")
    )
    encounters = (
        models.Encounter.objects.filter(patient_id=patient_id)
        .order_by("-encounter_date")
    )
    followups = (
        models.FollowupSeenEpisode.objects.filter(patient_id=patient_id)
        .order_by("-review_date")
    )
    return render(request, "clinic/patient_detail.html", {
        "patient": patient,
        "appointments": appointments,
        "episodes": episodes,
        "encounters": encounters,
        "followups": followups,
    })
