import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from . import forms, models


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
def todays_clinic(request):
    """Today's clinic — the day's appointment list with quick outcomes.

    Shows every appointment for a given day (defaults to today; ?date=YYYY-MM-DD
    to browse other days) and lets the team mark each patient Seen, Did-not-
    attend, or Cancelled without leaving the page. Every read and write is
    defensive so the page still renders when the DB isn't reachable.
    """
    # --- POST: record an outcome, then redirect back (PRG) ------------------
    if request.method == "POST":
        appt_id = (request.POST.get("appt_id") or "").strip()
        action = (request.POST.get("action") or "").strip()
        post_date = (request.POST.get("date") or "").strip()

        who_name = (request.user.get_full_name() or request.user.get_username())
        who_email = request.user.email or ""
        now = timezone.now()

        try:
            appt = models.Appointment.objects.filter(pk=appt_id).first()
        except Exception:
            appt = None

        if appt is None:
            messages.error(request, "Appointment not found.")
        elif action == "seen":
            appt.status = "seen"
            appt.outcome_recorded_at = now
            appt.outcome_recorded_by_name = who_name
            appt.outcome_recorded_by_email = who_email
            appt.cancelled_at = None
            appt.cancelled_by_name = None
            appt.cancelled_by_email = None
            appt.save()
            messages.success(request, f"Marked {appt.patient} as seen.")
        elif action == "dna":
            appt.status = "dna"
            appt.outcome_recorded_at = now
            appt.outcome_recorded_by_name = who_name
            appt.outcome_recorded_by_email = who_email
            appt.cancelled_at = None
            appt.cancelled_by_name = None
            appt.cancelled_by_email = None
            appt.save()
            messages.success(request, f"Marked {appt.patient} as did-not-attend.")
        elif action == "cancel":
            appt.status = "cancelled"
            appt.cancelled_at = now
            appt.cancelled_by_name = who_name
            appt.cancelled_by_email = who_email
            appt.save()
            messages.success(request, f"Cancelled {appt.patient}'s appointment.")
        elif action == "reopen":
            appt.status = "scheduled"
            appt.outcome_recorded_at = None
            appt.outcome_recorded_by_name = None
            appt.outcome_recorded_by_email = None
            appt.cancelled_at = None
            appt.cancelled_by_name = None
            appt.cancelled_by_email = None
            appt.save()
            messages.success(request, f"Reopened {appt.patient}'s appointment.")
        else:
            messages.error(request, "Unknown action.")

        url = reverse("clinic:todays_clinic")
        return redirect(f"{url}?date={post_date}" if post_date else url)

    # --- GET: which day are we viewing? -------------------------------------
    today = datetime.date.today()
    day = today
    raw_date = (request.GET.get("date") or "").strip()
    if raw_date:
        try:
            day = datetime.date.fromisoformat(raw_date)
        except ValueError:
            day = today

    try:
        appts = list(
            models.Appointment.objects
            .filter(appt_date=day)
            .select_related("patient", "assigned_to", "bank_staff")
            .order_by("appt_slot")
        )
    except Exception:
        appts = []

    # Outcome buckets for the summary strip.
    def _st(a):
        return (a.status or "").lower()

    seen = [a for a in appts if _st(a) in {"seen", "completed"}]
    dna = [a for a in appts if _st(a) == "dna"]
    cancelled = [a for a in appts if _st(a) == "cancelled"]
    done_ids = {a.id for a in seen} | {a.id for a in dna} | {a.id for a in cancelled}
    waiting = [a for a in appts if a.id not in done_ids]

    summary = {
        "total": len(appts),
        "waiting": len(waiting),
        "seen": len(seen),
        "dna": len(dna),
        "cancelled": len(cancelled),
    }

    return render(request, "clinic/todays_clinic.html", {
        "appts": appts,
        "summary": summary,
        "day": day,
        "is_today": day == today,
        "prev_day": day - datetime.timedelta(days=1),
        "next_day": day + datetime.timedelta(days=1),
        "today": today,
    })


@login_required
def patient_outcomes(request):
    today = datetime.date.today()
    P = models.Patient.objects

    counts = {
        "active": _safe_count(P.filter(followup_status="active")),
        "gozo": _safe_count(P.filter(followup_status="relocated_gozo")),
        "reversed": _safe_count(P.filter(followup_status="reversed")),
        "overseas": _safe_count(P.filter(followup_status="relocated_overseas")),
        "deceased": _safe_count(P.filter(followup_status="deceased")),
    }

    def fmt(v):
        return "—" if v is None else v

    stats = {k: fmt(v) for k, v in counts.items()}
    return render(request, "clinic/patient_outcomes.html", {"stats": stats})


@login_required
def registers(request):
    P = models.Patient.objects

    counts = {
        "inpatient": _safe_count(P.filter(followup_status="inpatient")),
    }

    def fmt(v):
        return "—" if v is None else v

    stats = {k: fmt(v) for k, v in counts.items()}
    return render(request, "clinic/registers.html", {"stats": stats})


@login_required
def discharge_letter(request):
    """Standalone Stoma discharge-letter generator.

    The template is a fully self-contained client-side tool (its own layout,
    print styles and localStorage state), so it does not extend base.html.
    """
    return render(request, "clinic/discharge_letter.html")


@login_required
def ordering_forms(request):
    """Ordering Forms landing page.

    Lists the appliance/supply ordering forms the stoma team uses. The
    destinations are wired up as they come online; the page renders from
    base.html so navigation and auth stay consistent with the rest of the app.
    """
    forms = [
        {
            "title": "Stoma Appliances",
            "desc": "Pouches, baseplates and one-piece / two-piece systems.",
            "url": "",
        },
        {
            "title": "Accessories & Supplies",
            "desc": "Barrier rings, pastes, powders, adhesive removers and belts.",
            "url": "",
        },
        {
            "title": "Prescription Request",
            "desc": "Request or renew a patient's appliance prescription.",
            "url": "",
        },
        {
            "title": "Ward / Stock Order",
            "desc": "Replenish ward stock and clinic consumables.",
            "url": "",
        },
    ]
    return render(request, "clinic/ordering_forms.html", {"forms": forms})


@login_required
def add_patient(request):
    """Dedicated page to add a new patient.

    Captures demographics, surgery details, clinical findings, medical and
    social history, and a data-protection selection, then creates the record
    and opens the new patient's detail page.
    """
    if request.method == "POST":
        form = forms.PatientForm(request.POST)
        if form.is_valid():
            patient = form.save()
            messages.success(request, "New patient added.")
            return redirect("clinic:patient_detail", patient_id=patient.id)
    else:
        form = forms.PatientForm()
    return render(request, "clinic/patient_form.html", {"form": form})


@login_required
def correspondence(request):
    """Correspondence hub — patient letters and communications.

    Landing page grouping the clinic's outgoing correspondence. The discharge
    letter generator is live; the rest are placeholders until wired up.
    """
    return render(request, "clinic/coming_soon.html", {
        "page_title": "Correspondence",
        "lead": "Patient letters and clinic communications in one place.",
        "links": [
            {"title": "Discharge Letter", "desc": "Generate a stoma discharge letter.",
             "url": "clinic:discharge_letter", "new_tab": True},
        ],
        "soon": [
            "GP / referral letters",
            "Clinic appointment letters",
            "Sent correspondence log",
        ],
    })


@login_required
def reminders(request):
    """Reminders hub — follow-ups and recalls that need action.

    Placeholder landing page for the reminders workflow (follow-ups due,
    patient recalls, task reminders) until the individual lists are built.
    """
    return render(request, "clinic/coming_soon.html", {
        "page_title": "Reminders",
        "lead": "Follow-ups, recalls and tasks that need attention.",
        "links": [
            {"title": "Follow-ups Due", "desc": "Patients due for review this month.",
             "url": "clinic:patient_list", "query": "?status=active"},
        ],
        "soon": [
            "Patient recall reminders",
            "Appointment reminders",
            "Personal task reminders",
        ],
    })


@login_required
def more_tools(request):
    """Landing page collecting the remaining dashboard tools.

    Gathers the buttons that don't yet have their own destination so none of
    them are dead links. Items with a `url` become live cards; the rest render
    as 'Coming soon'. Renders from base.html for consistent nav and auth.
    """
    tools = [
        {
            "title": "Surgical Rotation",
            "desc": "Theatre schedule and surgical rotation.",
            "url": "",
            "icon": "clock",
        },
        {
            "title": "Outpatient Clinic",
            "desc": "Clinic lists and reviews.",
            "url": "",
            "icon": "clinic",
        },
        {
            "title": "Appointments",
            "desc": "Scheduling and calendar.",
            "url": "",
            "icon": "calendar",
        },
        {
            "title": "Discharges (Post Operative)",
            "desc": "Post-operative discharge register.",
            "url": "",
            "icon": "doc",
        },
        {
            "title": "Temporary Paused",
            "desc": "Temporarily paused follow-ups.",
            "url": "",
            "icon": "pause",
        },
    ]
    return render(request, "clinic/more_tools.html", {"tools": tools})


@login_required
def patient_list(request):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    owner = (request.GET.get("owner") or "").strip()

    patients = models.Patient.objects.all().order_by("surname", "first_name")
    if q:
        patients = patients.filter(
            Q(first_name__icontains=q)
            | Q(surname__icontains=q)
            | Q(id_card__icontains=q)
            | Q(phone_number__icontains=q)
            | Q(locality__icontains=q)
        )
    if status:
        patients = patients.filter(followup_status=status)
    if owner:
        patients = patients.filter(followup_owner=owner)

    paginator = Paginator(patients, 40)
    page = paginator.get_page(request.GET.get("page"))

    statuses = (
        models.Patient.objects.exclude(followup_status__isnull=True)
        .exclude(followup_status="")
        .values_list("followup_status", flat=True)
        .distinct()
        .order_by("followup_status")
    )
    return render(request, "clinic/patient_list.html", {
        "page": page,
        "q": q,
        "status": status,
        "statuses": statuses,
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
