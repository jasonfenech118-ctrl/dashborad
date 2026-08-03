import calendar
import datetime
import time
import urllib.parse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMultiAlternatives
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
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

    # Outcome / register counts (always shown in their tab panels).
    outcome_counts = {
        "active": _safe_count(P.filter(followup_status="active")),
        "inpatient": _safe_count(P.filter(followup_status="inpatient")),
        "reversed": _safe_count(P.filter(followup_status="reversed")),
        "deceased": _safe_count(P.filter(followup_status="deceased")),
        "gozo": _safe_count(P.filter(followup_status="relocated_gozo")),
        "overseas": _safe_count(P.filter(followup_status="relocated_overseas")),
    }

    def fmt(v):
        return "—" if v is None else v

    stats = {k: fmt(v) for k, v in outcome_counts.items()}
    return render(request, "clinic/dashboard.html", {"stats": stats})


# Ordered list of the report metrics: (key, human label).
_METRIC_DEFS = [
    ("new_cases", "New Cases"),
    ("ileostomy", "Ileostomy"),
    ("colostomy", "Colostomy"),
    ("urostomy", "Urostomy"),
    ("followups", "Follow-ups"),
    ("emails", "Emails Responded"),
    ("inpatient_visits", "Inpatient Visits"),
    ("siting_sessions", "Stoma Siting Sessions"),
    ("total_stomas", "Total Stomas Formed"),
]


def _int_arg(value, default):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _range_for(period, year, month):
    """Return (date_from, date_to) for a whole month or whole year."""
    if period == "year":
        return datetime.date(year, 1, 1), datetime.date(year, 12, 31)
    date_from = datetime.date(year, month, 1)
    if month == 12:
        date_to = datetime.date(year, 12, 31)
    else:
        date_to = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)
    return date_from, date_to


def _stats_for_range(date_from, date_to):
    """Compute every report metric over a date range. None (DB error) -> 0."""
    P = models.Patient.objects
    E = models.Encounter.objects
    new_in_period = P.filter(surgery_date__gte=date_from, surgery_date__lte=date_to)
    raw = {
        "new_cases": _safe_count(new_in_period),
        "ileostomy": _safe_count(new_in_period.filter(stoma_type_summary__icontains="ileostomy")),
        "colostomy": _safe_count(new_in_period.filter(stoma_type_summary__icontains="colostomy")),
        "urostomy": _safe_count(new_in_period.filter(stoma_type_summary__icontains="urostomy")),
        "followups": _safe_count(
            models.FollowupSeenEpisode.objects.filter(
                review_date__gte=date_from, review_date__lte=date_to,
            )
        ),
        "emails": _safe_count(
            E.filter(encounter_date__gte=date_from, encounter_date__lte=date_to,
                     encounter_type__icontains="email")
        ),
        "inpatient_visits": _safe_count(
            E.filter(encounter_date__gte=date_from, encounter_date__lte=date_to,
                     encounter_type__icontains="inpatient")
        ),
        "siting_sessions": _safe_count(
            E.filter(encounter_date__gte=date_from, encounter_date__lte=date_to,
                     encounter_type__icontains="siting")
        ),
    }
    raw["total_stomas"] = raw["new_cases"]
    return {k: (0 if v is None else v) for k, v in raw.items()}


@login_required
def reports(request):
    today = datetime.date.today()

    period = (request.GET.get("period") or "month").strip()
    sel_year = _int_arg(request.GET.get("year"), today.year)
    sel_month = max(1, min(12, _int_arg(request.GET.get("month"), today.month)))

    # Default comparison period: the previous month (or previous year).
    if period == "year":
        def_cyear, def_cmonth = sel_year - 1, sel_month
    elif sel_month == 1:
        def_cyear, def_cmonth = sel_year - 1, 12
    else:
        def_cyear, def_cmonth = sel_year, sel_month - 1
    cmp_year = _int_arg(request.GET.get("cyear"), def_cyear)
    cmp_month = max(1, min(12, _int_arg(request.GET.get("cmonth"), def_cmonth)))

    cur = _stats_for_range(*_range_for(period, sel_year, sel_month))
    cmp = _stats_for_range(*_range_for(period, cmp_year, cmp_month))

    metrics = [
        {"key": key, "label": label, "cur": cur[key], "cmp": cmp[key],
         "delta": cur[key] - cmp[key]}
        for key, label in _METRIC_DEFS
    ]
    chart_max = max([1] + [m["cur"] for m in metrics] + [m["cmp"] for m in metrics])

    month_names = {i: calendar.month_name[i] for i in range(1, 13)}
    year_range = list(range(today.year - 5, today.year + 2))

    if period == "year":
        sel_label, cmp_label = str(sel_year), str(cmp_year)
    else:
        sel_label = f"{month_names[sel_month]} {sel_year}"
        cmp_label = f"{month_names[cmp_month]} {cmp_year}"

    file_tag = f"{sel_year}-{sel_month:02d}" if period == "month" else str(sel_year)

    pie_stoma_cur = [
        {"label": "Ileostomy", "value": cur["ileostomy"]},
        {"label": "Colostomy", "value": cur["colostomy"]},
        {"label": "Urostomy", "value": cur["urostomy"]},
    ]
    pie_stoma_cmp = [
        {"label": "Ileostomy", "value": cmp["ileostomy"]},
        {"label": "Colostomy", "value": cmp["colostomy"]},
        {"label": "Urostomy", "value": cmp["urostomy"]},
    ]
    pie_activity_cur = [
        {"label": "Follow-ups", "value": cur["followups"]},
        {"label": "Emails", "value": cur["emails"]},
        {"label": "Inpatient Visits", "value": cur["inpatient_visits"]},
        {"label": "Siting Sessions", "value": cur["siting_sessions"]},
    ]
    pie_activity_cmp = [
        {"label": "Follow-ups", "value": cmp["followups"]},
        {"label": "Emails", "value": cmp["emails"]},
        {"label": "Inpatient Visits", "value": cmp["inpatient_visits"]},
        {"label": "Siting Sessions", "value": cmp["siting_sessions"]},
    ]

    report_data = {
        "sel_label": sel_label,
        "cmp_label": cmp_label,
        "file_tag": file_tag,
        "metrics": [{"label": m["label"], "cur": m["cur"], "cmp": m["cmp"],
                      "delta": m["delta"]} for m in metrics],
        "pie_stoma_cur": pie_stoma_cur,
        "pie_stoma_cmp": pie_stoma_cmp,
        "pie_activity_cur": pie_activity_cur,
        "pie_activity_cmp": pie_activity_cmp,
    }

    return render(request, "clinic/reports.html", {
        "metrics": metrics,
        "chart_max": chart_max,
        "period": period,
        "sel_year": sel_year,
        "sel_month": sel_month,
        "sel_month_name": month_names.get(sel_month, ""),
        "cmp_year": cmp_year,
        "cmp_month": cmp_month,
        "sel_label": sel_label,
        "cmp_label": cmp_label,
        "month_names": month_names,
        "year_range": year_range,
        "report_data": report_data,
    })


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
def ordering_forms(request):
    """Ordering Forms landing page.

    Lists the appliance/supply ordering forms the stoma team uses. The
    destinations are wired up as they come online; the page renders from
    base.html so navigation and auth stay consistent with the rest of the app.
    """
    forms = [
        {
            "title": "Extra Supplies Requisition (ESRF STO-01)",
            "desc": "Extra supplies requisition form for Stoma Care — Logistics Department, Mater Dei Hospital.",
            "url": "/ordering/esrf/",
        },
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


def _user_full_name(user):
    """Best display name for the signature line: full name, else username."""
    full = (user.get_full_name() or "").strip()
    return full or user.get_username()


def _email_configured():
    """True when a real SMTP backend is configured (not the console stub)."""
    return "smtp" in (settings.EMAIL_BACKEND or "").lower()


def _next_reference():
    """Sequential per-day reference, e.g. ESRF-STO01-20260803-001."""
    today = datetime.date.today()
    prefix = f"ESRF-STO01-{today:%Y%m%d}"
    try:
        n = models.OrderingDocument.objects.filter(reference__startswith=prefix).count() + 1
        ref = f"{prefix}-{n:03d}"
        while models.OrderingDocument.objects.filter(reference=ref).exists():
            n += 1
            ref = f"{prefix}-{n:03d}"
        return ref
    except Exception:
        # DB unreachable — fall back to a timestamp-unique reference.
        return f"{prefix}-{int(time.time())}"


def _parse_items(request):
    """Pull the line-item arrays from the POST into a clean list of dicts.

    Empty rows (no code and no description) are dropped.
    """
    codes = request.POST.getlist("code")
    descs = request.POST.getlist("description")
    apps = request.POST.getlist("app")
    efs = request.POST.getlist("ef")
    reasons = request.POST.getlist("reason")
    rows = []
    for i in range(max(len(codes), len(descs), len(apps), len(efs), len(reasons))):
        def get(lst):
            return (lst[i] if i < len(lst) else "").strip()
        code, desc = get(codes), get(descs)
        if not code and not desc:
            continue
        rows.append({
            "code": code, "description": desc,
            "app": get(apps), "ef": get(efs), "reason": get(reasons),
        })
    return rows


def _send_order_email(doc):
    """Render and send the requisition to Logistics. Raises on failure."""
    subject = f"Extra Supplies Requisition — {doc.section_ward} ({doc.reference})"
    ctx = {"doc": doc}
    html_body = render_to_string("clinic/email/esrf_order.html", ctx)
    text_body = render_to_string("clinic/email/esrf_order.txt", ctx)
    recipient = doc.recipient_email or settings.LOGISTICS_EMAIL
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)


def _mailto_link(doc):
    """A fallback mailto: link so the user can send from their own client."""
    lines = [
        "Extra Supplies Requisition Form",
        f"Reference: {doc.reference}",
        f"Section/Ward: {doc.section_ward}",
        f"Cost Centre: {doc.cost_centre}",
        f"Ext no.: {doc.ext_no or ''}",
        f"Scheduled delivery: {doc.delivery_period or ''}",
        "",
        "Items:",
    ]
    for it in (doc.items or []):
        if it.get("code") or it.get("description"):
            lines.append(
                f"  - {it.get('code','')}  {it.get('description','')}  "
                f"APP: {it.get('app','')}  Reason: {it.get('reason','')}"
            )
    lines += ["", f"Requested by: {doc.requested_by_name or ''}",
              f"Date: {doc.form_date or ''}"]
    body = "\r\n".join(lines)
    subject = f"Extra Supplies Requisition — {doc.section_ward} ({doc.reference})"
    recipient = doc.recipient_email or settings.LOGISTICS_EMAIL
    return (
        f"mailto:{recipient}?subject={urllib.parse.quote(subject)}"
        f"&body={urllib.parse.quote(body)}"
    )


@login_required
def esrf_form(request):
    """The fillable Extra Supplies Requisition Form.

    GET renders the form (name + date pre-filled from the logged-in user).
    POST saves the submission to the Clinic Documents archive and emails it
    to Logistics.
    """
    if request.method == "POST":
        return _esrf_submit(request)

    return render(request, "clinic/esrf_form.html", {
        "user_full_name": _user_full_name(request.user),
        "today": datetime.date.today(),
        "logistics_email": settings.LOGISTICS_EMAIL,
    })


def _esrf_submit(request):
    items = _parse_items(request)
    if not items:
        messages.error(request, "Add at least one item before sending.")
        return render(request, "clinic/esrf_form.html", {
            "user_full_name": _user_full_name(request.user),
            "today": datetime.date.today(),
            "logistics_email": settings.LOGISTICS_EMAIL,
        })

    raw_date = (request.POST.get("form_date") or "").strip()
    try:
        form_date = datetime.date.fromisoformat(raw_date) if raw_date else datetime.date.today()
    except ValueError:
        form_date = datetime.date.today()

    doc = models.OrderingDocument(
        reference=_next_reference(),
        form_type="ESRF STO-01",
        section_ward="Stoma Care",
        cost_centre="STO-01",
        ext_no=(request.POST.get("ext_no") or "").strip(),
        delivery_period=(request.POST.get("delivery_period") or "").strip(),
        items=items,
        requested_by_name=(request.POST.get("requested_by") or "").strip()
                          or _user_full_name(request.user),
        requested_by_username=request.user.get_username(),
        form_date=form_date,
        recipient_email=settings.LOGISTICS_EMAIL,
        status=models.OrderingDocument.STATUS_SAVED,
    )

    # Try to email it, then persist the outcome.
    email_ok, email_note = False, ""
    if _email_configured():
        try:
            _send_order_email(doc)
            email_ok = True
        except Exception as exc:  # noqa: BLE001 — surface any send error to the user
            email_note = f"Email could not be sent ({exc}). The form was saved."
    else:
        email_note = ("Email sending isn't set up yet, so the form was saved to "
                      "Clinic Documents but not sent automatically.")

    if email_ok:
        doc.status = models.OrderingDocument.STATUS_SENT
        doc.sent_at = timezone.now()

    saved = True
    try:
        doc.save()
    except Exception:
        saved = False

    if email_ok:
        messages.success(
            request,
            f"Requisition {doc.reference} sent to {doc.recipient_email} and "
            f"saved to Clinic Documents.",
        )
    elif saved:
        messages.warning(request, email_note)
    else:
        messages.error(
            request,
            "The database is unavailable, so the form could not be saved. "
            "Please try again shortly.",
        )
        return redirect("clinic:esrf_form")

    return redirect("clinic:ordering_document_detail", pk=doc.pk)


@login_required
def clinic_documents(request):
    """Clinic Documents archive — every ordering form sent from the app."""
    q = (request.GET.get("q") or "").strip()
    documents, db_ok = [], True
    try:
        qs = models.OrderingDocument.objects.all()
        if q:
            qs = qs.filter(
                Q(reference__icontains=q)
                | Q(requested_by_name__icontains=q)
                | Q(section_ward__icontains=q)
            )
        documents = list(qs[:200])
    except Exception:
        db_ok = False
    return render(request, "clinic/clinic_documents.html", {
        "documents": documents,
        "db_ok": db_ok,
        "q": q,
    })


@login_required
def ordering_document_detail(request, pk):
    """Read-only view of an archived requisition (printable)."""
    doc = get_object_or_404(models.OrderingDocument, pk=pk)
    return render(request, "clinic/ordering_document.html", {
        "doc": doc,
        "mailto": _mailto_link(doc),
        "is_sent": doc.status == models.OrderingDocument.STATUS_SENT,
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
