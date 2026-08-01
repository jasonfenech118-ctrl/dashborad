import calendar
import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
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
def surgical_rotation(request):
    """Surgical rotation — theatre schedule from the patients' surgery dates.

    Upcoming planned surgeries plus the last 60 days of performed surgeries,
    both defensive so the page renders even when the DB is unreachable.
    """
    today = datetime.date.today()
    P = models.Patient.objects

    try:
        upcoming = list(
            P.filter(planned_surgery_date__gte=today)
            .order_by("planned_surgery_date", "surname", "first_name")[:100]
        )
    except Exception:
        upcoming = []
    try:
        recent = list(
            P.filter(
                surgery_date__lte=today,
                surgery_date__gte=today - datetime.timedelta(days=60),
            )
            .order_by("-surgery_date", "surname", "first_name")[:100]
        )
    except Exception:
        recent = []

    return render(request, "clinic/surgical_rotation.html", {
        "upcoming": upcoming,
        "recent": recent,
        "today": today,
    })


@login_required
def appointments(request):
    """Appointments — a two-week schedule grouped by day.

    Defaults to the fortnight starting today; ?from=YYYY-MM-DD moves the
    window. Each day links through to Today's Clinic for outcome recording.
    """
    today = datetime.date.today()
    start = today
    raw = (request.GET.get("from") or "").strip()
    if raw:
        try:
            start = datetime.date.fromisoformat(raw)
        except ValueError:
            start = today
    end = start + datetime.timedelta(days=13)

    try:
        appts = list(
            models.Appointment.objects
            .filter(appt_date__gte=start, appt_date__lte=end)
            .select_related("patient", "assigned_to", "bank_staff")
            .order_by("appt_date", "appt_slot")
        )
    except Exception:
        appts = []

    by_date = {}
    for a in appts:
        by_date.setdefault(a.appt_date, []).append(a)
    days = [{"date": d, "appts": items} for d, items in sorted(by_date.items())]

    return render(request, "clinic/appointments.html", {
        "days": days,
        "start": start,
        "end": end,
        "today": today,
        "total": len(appts),
        "prev_start": start - datetime.timedelta(days=14),
        "next_start": start + datetime.timedelta(days=14),
        "is_current": start == today,
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


# Query fragments shared by the Registers page and the patient-list register
# filters, so the count on a button always matches the list it opens.
REGISTER_QUERIES = {
    "discharges": lambda P: P.filter(discharged_date__isnull=False),
    "paused": lambda P: P.filter(
        Q(followup_status__icontains="pause")
        | Q(patient_status_raw__icontains="pause")
    ),
}

REGISTER_LABELS = {
    "discharges": "Discharges (Post Operative)",
    "paused": "Temporary Paused",
}


@login_required
def registers(request):
    P = models.Patient.objects

    counts = {
        "inpatient": _safe_count(P.filter(followup_status="inpatient")),
        "discharges": _safe_count(REGISTER_QUERIES["discharges"](P)),
        "paused": _safe_count(REGISTER_QUERIES["paused"](P)),
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


# Printable ordering forms, keyed by URL slug. Each renders through the shared
# clinic/ordering_form.html template as a fill-in-and-print order sheet.
ORDER_FORMS = {
    "stoma-appliances": {
        "title": "Stoma Appliances Order",
        "desc": "Pouches, baseplates and one-piece / two-piece systems.",
        "items": [
            "One-piece drainable pouch",
            "One-piece closed pouch",
            "Two-piece baseplate",
            "Two-piece drainable pouch",
            "Two-piece closed pouch",
            "Urostomy pouch",
            "High-output pouch",
            "Paediatric pouch",
        ],
    },
    "accessories-supplies": {
        "title": "Accessories & Supplies Order",
        "desc": "Barrier rings, pastes, powders, adhesive removers and belts.",
        "items": [
            "Barrier ring / seal",
            "Stoma paste",
            "Stoma powder",
            "Barrier film wipes / spray",
            "Adhesive remover wipes / spray",
            "Support belt",
            "Flange extenders",
            "Night drainage bag",
        ],
    },
    "prescription-request": {
        "title": "Prescription Request",
        "desc": "Request or renew a patient's appliance prescription.",
        "items": [
            "Pouches (per month)",
            "Baseplates (per month)",
            "Barrier rings / seals (per month)",
            "Stoma paste (per month)",
            "Adhesive remover (per month)",
            "Barrier film (per month)",
        ],
    },
    "ward-stock": {
        "title": "Ward / Stock Order",
        "desc": "Replenish ward stock and clinic consumables.",
        "items": [
            "Drainable pouches (assorted)",
            "Closed pouches (assorted)",
            "Baseplates (assorted sizes)",
            "Barrier rings / seals",
            "Stoma paste",
            "Stoma powder",
            "Adhesive remover",
            "Measuring guides",
            "Gloves",
            "Gauze / wipes",
        ],
    },
}


@login_required
def ordering_forms(request):
    """Ordering Forms landing page.

    Lists the appliance/supply ordering forms the stoma team uses. Every card
    opens its printable order form.
    """
    forms = [
        {
            "title": "Stoma Appliances",
            "desc": ORDER_FORMS["stoma-appliances"]["desc"],
            "url": reverse("clinic:ordering_form_detail", args=["stoma-appliances"]),
        },
        {
            "title": "Accessories & Supplies",
            "desc": ORDER_FORMS["accessories-supplies"]["desc"],
            "url": reverse("clinic:ordering_form_detail", args=["accessories-supplies"]),
        },
        {
            "title": "Prescription Request",
            "desc": ORDER_FORMS["prescription-request"]["desc"],
            "url": reverse("clinic:ordering_form_detail", args=["prescription-request"]),
        },
        {
            "title": "Ward / Stock Order",
            "desc": ORDER_FORMS["ward-stock"]["desc"],
            "url": reverse("clinic:ordering_form_detail", args=["ward-stock"]),
        },
    ]
    return render(request, "clinic/ordering_forms.html", {"forms": forms})


@login_required
def ordering_form_detail(request, slug):
    """A single printable ordering form (fill in on screen, then print)."""
    cfg = ORDER_FORMS.get(slug)
    if cfg is None:
        raise Http404("Unknown ordering form")
    return render(request, "clinic/ordering_form.html", {
        "cfg": cfg,
        "blank_rows": range(6),
    })


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

    Landing page grouping the clinic's outgoing correspondence. All three
    letter generators are live; a sent-correspondence log will follow once
    letters are stored server-side.
    """
    return render(request, "clinic/coming_soon.html", {
        "page_title": "Correspondence",
        "lead": "Patient letters and clinic communications in one place.",
        "links": [
            {"title": "Discharge Letter", "desc": "Generate a stoma discharge letter.",
             "url": "clinic:discharge_letter", "new_tab": True},
            {"title": "GP / Referral Letter", "desc": "Write and print a letter to the patient's GP or a referral.",
             "url": "clinic:gp_letter"},
            {"title": "Appointment Letter", "desc": "Print an appointment notification letter for a patient.",
             "url": "clinic:appointment_letter"},
        ],
        "soon": [
            "Sent correspondence log",
        ],
    })


@login_required
def gp_letter(request):
    """GP / referral letter — fill in on screen, print on clinic letterhead."""
    return render(request, "clinic/gp_letter.html")


@login_required
def appointment_letter(request):
    """Appointment notification letter — fill in on screen and print."""
    return render(request, "clinic/appointment_letter.html")


@login_required
def reminders(request):
    """Reminders — the follow-up recall worklist.

    Shows every active patient due for follow-up in the selected month
    (defaults to the current month, ?month=&year= to browse), grouped by
    follow-up owner with phone numbers, plus an overdue section for active
    patients whose due month has already passed.
    """
    today = datetime.date.today()
    month, year = today.month, today.year
    try:
        month = int(request.GET.get("month") or month)
        year = int(request.GET.get("year") or year)
    except (TypeError, ValueError):
        month, year = today.month, today.year
    if not 1 <= month <= 12:
        month = today.month
    if not 2000 <= year <= 2100:
        year = today.year

    P = models.Patient.objects
    try:
        due = list(
            P.filter(
                followup_status="active",
                followup_due_month=month,
                followup_year=year,
            ).order_by("followup_owner", "surname", "first_name")
        )
    except Exception:
        due = []

    try:
        overdue = list(
            P.filter(followup_status="active")
            .exclude(followup_due_month__isnull=True)
            .exclude(followup_year__isnull=True)
            .filter(
                Q(followup_year__lt=year)
                | Q(followup_year=year, followup_due_month__lt=month)
            )
            .order_by("followup_year", "followup_due_month", "surname")[:200]
        )
    except Exception:
        overdue = []

    def due_label(p):
        try:
            return f"{calendar.month_abbr[p.followup_due_month]} {p.followup_year}"
        except Exception:
            return "—"

    for p in overdue:
        p.due_label = due_label(p)

    by_owner = {}
    for p in due:
        by_owner.setdefault(p.followup_owner or "Unassigned", []).append(p)
    owners = [{"owner": k, "patients": by_owner[k]} for k in sorted(by_owner)]

    prev_m, prev_y = (12, year - 1) if month == 1 else (month - 1, year)
    next_m, next_y = (1, year + 1) if month == 12 else (month + 1, year)

    return render(request, "clinic/reminders.html", {
        "month": month,
        "year": year,
        "month_name": calendar.month_name[month],
        "prev_m": prev_m, "prev_y": prev_y,
        "next_m": next_m, "next_y": next_y,
        "owners": owners,
        "due_count": len(due),
        "overdue": overdue,
        "is_current": (month, year) == (today.month, today.year),
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
            "url": reverse("clinic:surgical_rotation"),
            "icon": "clock",
        },
        {
            "title": "Appointments",
            "desc": "Two-week appointment schedule.",
            "url": reverse("clinic:appointments"),
            "icon": "calendar",
        },
        {
            "title": "Discharges (Post Operative)",
            "desc": "Post-operative discharge register.",
            "url": reverse("clinic:patient_list") + "?register=discharges",
            "icon": "doc",
        },
        {
            "title": "Temporary Paused",
            "desc": "Temporarily paused follow-ups.",
            "url": reverse("clinic:patient_list") + "?register=paused",
            "icon": "pause",
        },
    ]
    return render(request, "clinic/more_tools.html", {"tools": tools})


@login_required
def patient_list(request):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    owner = (request.GET.get("owner") or "").strip()
    register = (request.GET.get("register") or "").strip()
    if register not in REGISTER_QUERIES:
        register = ""

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
    if register:
        patients = REGISTER_QUERIES[register](patients)

    # Defensive, like the rest of the app: still render (empty) when the DB
    # isn't reachable rather than 500.
    try:
        paginator = Paginator(patients, 40)
        page = paginator.get_page(request.GET.get("page"))
        page.object_list = list(page.object_list)
    except Exception:
        paginator = Paginator([], 40)
        page = paginator.get_page(1)

    try:
        statuses = list(
            models.Patient.objects.exclude(followup_status__isnull=True)
            .exclude(followup_status="")
            .values_list("followup_status", flat=True)
            .distinct()
            .order_by("followup_status")
        )
    except Exception:
        statuses = []
    return render(request, "clinic/patient_list.html", {
        "page": page,
        "q": q,
        "status": status,
        "statuses": statuses,
        "register": register,
        "register_label": REGISTER_LABELS.get(register, ""),
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
