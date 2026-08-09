import calendar
import datetime
import json
import re
import time
import urllib.parse

from django.core.files.base import ContentFile

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.mail import EmailMultiAlternatives
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from . import forms, models, order_forms as order_form_defs


def _safe_query(fn, default=None):
    """Run a query, tolerating a missing table or an unreachable database.

    The atomic() block matters: on PostgreSQL a failed statement aborts the
    whole transaction, so simply catching the error would leave the
    connection poisoned and every later query in the request would fail too
    (the response then dies mid-flight). Running inside a savepoint rolls
    just this query back and leaves the connection usable.
    """
    try:
        with transaction.atomic():
            return fn()
    except Exception:
        return default


def _safe_count(qs):
    """Return a count, or None if the table/DB isn't reachable yet."""
    return _safe_query(qs.count, None)


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
    return render(request, "clinic/dashboard.html", {
        "stats": stats,
        "reminders_due": _reminders_due_today() or [],
    })


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
def discharge_letter(request, patient_id=None):
    """Stoma discharge-letter generator.

    The template is a self-contained client-side tool. When opened for a
    specific patient their details (and current stoma) are handed to the page
    so the letter starts pre-filled instead of blank.
    """
    prefill = None
    if patient_id:
        patient = get_object_or_404(models.Patient, pk=patient_id)
        sex = (patient.sex or "").strip().lower()
        stoma = None
        stoma = _safe_query(
            lambda: patient.stomas.filter(status=models.Stoma.ACTIVE).first(), None)
        prefill = {
            "patient_id": str(patient.id),
            "title": "Ms" if sex.startswith("f") else ("Mr" if sex.startswith("m") else ""),
            "first_name": patient.first_name or "",
            "surname": patient.surname or "",
            "id_card": patient.id_card or "",
            "consultant": patient.consultant or "",
            "stoma_type": (stoma.get_stoma_type_display() if stoma
                           else (patient.stoma_type_summary or "")),
            "operation": patient.operation_performed or "",
            "surgery_date": patient.surgery_date.strftime("%d/%m/%Y") if patient.surgery_date else "",
        }
    return render(request, "clinic/discharge_letter.html", {
        "prefill_json": json.dumps(prefill) if prefill else "null",
    })


# ------------------------------------------------------- stomas & encounters


def _apply_patient_status_rules(patient):
    """Keep the patient's status in step with their stomas.

    A reversed stoma with nothing else in place makes the patient inactive
    (reversed); a deceased patient closes every open pathway.
    """
    stomas = _safe_query(lambda: list(patient.stomas.all()), None)
    if stomas is None:
        return
    if not stomas:
        return

    open_stomas = [s for s in stomas if s.is_open]
    reversed_any = any(s.status == models.Stoma.REVERSED for s in stomas)

    if not open_stomas and reversed_any:
        if patient.followup_status != "reversed":
            patient.followup_status = "reversed"
            try:
                patient.save(update_fields=["followup_status"])
            except Exception:
                pass
        # The episode is finished once the stoma is reversed.
        try:
            models.CarePathway.objects.filter(patient_id=patient.id).exclude(
                status=models.CarePathway.CLOSED
            ).update(status=models.CarePathway.CLOSED)
        except Exception:
            pass


def _close_case_for_deceased(patient, date_of_death=None):
    """Mark a patient deceased and close their case automatically."""
    patient.followup_status = "deceased"
    if date_of_death:
        patient.rip_date = date_of_death
    try:
        patient.save(update_fields=["followup_status", "rip_date"])
    except Exception:
        try:
            patient.save()
        except Exception:
            pass
    try:
        models.CarePathway.objects.filter(patient_id=patient.id).exclude(
            status=models.CarePathway.CLOSED
        ).update(status=models.CarePathway.CLOSED)
    except Exception:
        pass


@login_required
def encounter_new(request, pk):
    """Record a full encounter on a pathway: assessment, appliance, report."""
    pathway = get_object_or_404(models.CarePathway, pk=pk)
    if request.method == "POST":
        return _save_encounter(request, pathway)
    stomas = list(pathway.patient.stomas.all()) if _safe(lambda: pathway.patient) else []
    return render(request, "clinic/encounter_form.html", {
        "p": pathway, "stomas": stomas, "today": datetime.date.today(),
    })


def _safe(fn, default=None):
    return _safe_query(fn, default)


def _save_encounter(request, p):
    E = models.PathwayEvent
    who = request.user.get_username()
    today = datetime.date.today()
    d = _parse_date(request.POST.get("event_date"), today)

    is_post_op = p.surgery_date is not None
    day = (d - p.surgery_date).days if is_post_op else None
    first = is_post_op and p.first_review_date is None
    if first:
        p.first_review_date = d
        p.save(update_fields=["first_review_date", "updated_at"])

    event = E.objects.create(
        pathway=p,
        event_type=E.POST_OP_REVIEW if is_post_op else E.REVIEW,
        event_date=d, day_number=day,
        summary=(request.POST.get("summary") or "").strip() or None,
        education_given=bool(request.POST.get("education_given")),
        supplies_given=bool(request.POST.get("supplies_given")),
        notes=(request.POST.get("report") or "").strip() or None,
        recorded_by=who,
    )

    # Stoma assessments — one per stoma the nurse filled in.
    for sid in request.POST.getlist("assess_stoma"):
        colour = (request.POST.get(f"colour_{sid}") or "").strip()
        output = (request.POST.get(f"output_{sid}") or "").strip()
        skin = (request.POST.get(f"skin_{sid}") or "").strip()
        height = (request.POST.get(f"height_{sid}") or "").strip()
        comps = (request.POST.get(f"comps_{sid}") or "").strip()
        anote = (request.POST.get(f"anote_{sid}") or "").strip()
        if not any([colour, output, skin, height, comps, anote]):
            continue
        try:
            models.StomaAssessment.objects.create(
                stoma_id=sid, event=event, assessed_on=d,
                colour=colour or None, output=output or None,
                output_ml=(request.POST.get(f"outml_{sid}") or "").strip() or None,
                peristomal_skin=skin or None, stoma_height=height or None,
                complications=comps or None, notes=anote or None,
            )
        except Exception:
            pass

    # Appliance used / changed.
    if request.POST.get("appliance_used"):
        try:
            models.ApplianceRecord.objects.create(
                patient_id=p.patient_id,
                stoma_id=(request.POST.get("appliance_stoma") or None) or None,
                event=event, used_on=d,
                system=(request.POST.get("app_system") or "").strip() or None,
                pouch_type=(request.POST.get("app_pouch") or "").strip() or None,
                brand=(request.POST.get("app_brand") or "").strip() or None,
                product_code=(request.POST.get("app_code") or "").strip() or None,
                size=(request.POST.get("app_size") or "").strip() or None,
                accessories=(request.POST.get("app_acc") or "").strip() or None,
                changed=bool(request.POST.get("app_changed")),
            )
        except Exception:
            pass

    if request.POST.get("close_episode"):
        p.discharge_date = p.discharge_date or d
        p.status = (models.CarePathway.FOLLOWUP if p.expects_followup
                    else models.CarePathway.CLOSED)
        p.save()
        E.objects.create(pathway=p, event_type=E.DISCHARGE, event_date=d,
                         summary="Episode closed", recorded_by=who)
        messages.success(request, f"Encounter {event.encounter_number} saved and episode closed.")
        return redirect("clinic:pathway_detail", pk=p.pk)

    if first and p.first_review_was_late:
        messages.warning(
            request,
            f"Encounter {event.encounter_number} saved. First post-op review was "
            f"day {p.first_review_delay_days} (not day 1) — flagged on this episode.",
        )
    else:
        messages.success(request, f"Encounter {event.encounter_number} saved.")
    return redirect("clinic:pathway_detail", pk=p.pk)


@login_required
def patient_profile(request, patient_id):
    """At-a-glance profile: stomas, appliances, episodes and history."""
    patient = get_object_or_404(models.Patient, pk=patient_id)

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "add_stoma":
            try:
                models.Stoma.objects.create(
                    patient=patient,
                    pathway_id=(request.POST.get("pathway") or None) or None,
                    stoma_type=(request.POST.get("stoma_type") or "").strip(),
                    site=(request.POST.get("site") or "").strip() or None,
                    formed_date=_parse_date(request.POST.get("formed_date")),
                    notes=(request.POST.get("notes") or "").strip() or None,
                )
                messages.success(request, "Stoma added.")
            except Exception:
                messages.error(request, "Could not add that stoma.")
        elif action == "stoma_change":
            try:
                stoma = models.Stoma.objects.get(pk=request.POST.get("stoma_id"))
                ctype = (request.POST.get("change_type") or "").strip()
                cdate = _parse_date(request.POST.get("change_date"), datetime.date.today())
                new_site = (request.POST.get("new_site") or "").strip() or None
                models.StomaChange.objects.create(
                    stoma=stoma, change_type=ctype, change_date=cdate,
                    new_site=new_site,
                    notes=(request.POST.get("change_notes") or "").strip() or None,
                    recorded_by=request.user.get_username(),
                )
                # Reflect the change on the stoma itself.
                if ctype in {models.Stoma.CLOSED, models.Stoma.REVERSED}:
                    stoma.status = ctype
                    stoma.ended_date = cdate
                elif ctype == "resited":
                    stoma.status = models.Stoma.RESITED
                    if new_site:
                        stoma.site = new_site
                elif ctype == "refashioned":
                    stoma.status = models.Stoma.REFASHIONED
                stoma.save()
                _apply_patient_status_rules(patient)
                patient.refresh_from_db()
                messages.success(request, f"{stoma.stoma_ref} marked {ctype}.")
            except Exception:
                messages.error(request, "Could not record that change.")
        elif action == "mark_deceased":
            _close_case_for_deceased(
                patient, _parse_date(request.POST.get("rip_date"), datetime.date.today())
            )
            messages.success(request, "Patient marked deceased — case closed.")
        return redirect("clinic:patient_profile", patient_id=patient.id)

    stomas = _safe(lambda: list(patient.stomas.all()), []) or []
    for s in stomas:
        s.change_list = _safe(lambda s=s: list(s.changes.all()), []) or []
        s.appliance_count = _safe(lambda s=s: s.appliances.count(), 0) or 0
    pathways = _safe(
        lambda: list(models.CarePathway.objects.filter(patient_id=patient.id)), []
    ) or []
    appliances = _safe(
        lambda: list(models.ApplianceRecord.objects.filter(patient_id=patient.id)[:50]), []
    ) or []
    events = _safe(
        lambda: list(models.PathwayEvent.objects.filter(
            pathway__patient_id=patient.id).select_related("pathway")[:100]), []
    ) or []

    sex = (patient.sex or "").strip().lower()
    silhouette = "female" if sex.startswith("f") else ("male" if sex.startswith("m") else "unknown")
    active_case = (patient.followup_status or "") not in {"reversed", "deceased"}

    return render(request, "clinic/patient_profile.html", {
        "patient": patient,
        "stomas": stomas,
        "open_stomas": [s for s in stomas if s.is_open],
        "pathways": pathways,
        "appliances": appliances,
        "events": events,
        "silhouette": silhouette,
        "active_case": active_case,
        "stoma_types": models.Stoma.TYPE_CHOICES,
        "site_choices": models.Stoma.SITE_CHOICES,
        "change_types": models.StomaChange.TYPE_CHOICES,
        "today": datetime.date.today(),
    })


@login_required
def ordering_forms(request):
    """Ordering Forms landing page.

    Lists the appliance/supply ordering forms the stoma team uses. The
    destinations are wired up as they come online; the page renders from
    base.html so navigation and auth stay consistent with the rest of the app.
    """
    forms = [
        {
            "title": "Extra Supplies Requisition ESRF",
            "desc": "",
            "url": "/ordering/esrf/",
        },
        {
            "title": "MML Part 1",
            "desc": "",
            "url": reverse("clinic:order_form", args=["mmml-topup"]),
        },
        {
            "title": "MML Part 2",
            "desc": "",
            "url": reverse("clinic:order_form", args=["cleaning"]),
        },
        {
            "title": "Stationary",
            "desc": "",
            "url": reverse("clinic:order_form", args=["stationery"]),
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


def _next_reference(prefix="ESRF-STO01"):
    """Sequential per-day reference, e.g. ESRF-STO01-20260803-001."""
    today = datetime.date.today()
    prefix = f"{prefix}-{today:%Y%m%d}"
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

    # File a copy of the correspondence in the Library, so every requisition
    # sent to Logistics is kept alongside the rest of the clinic's documents.
    if saved:
        _file_in_library(
            title=f"Requisition {doc.reference} — {doc.section_ward}",
            category=models.LibraryDocument.CORRESPONDENCE
                     if email_ok else models.LibraryDocument.REQUISITION,
            source=models.LibraryDocument.SOURCE_REQUISITION,
            html=render_to_string("clinic/email/esrf_order.html", {"doc": doc}),
            reference=doc.reference,
            description=(f"Emailed to {doc.recipient_email} on "
                         f"{timezone.now():%d/%m/%Y}." if email_ok
                         else "Prepared but not emailed."),
            by=request.user.get_username(),
        )

    if email_ok:
        messages.success(
            request,
            f"Requisition {doc.reference} sent to {doc.recipient_email}, and "
            f"saved to Clinic Documents and the Library.",
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
    def _load():
        qs = models.OrderingDocument.objects.all()
        if q:
            qs = qs.filter(
                Q(reference__icontains=q)
                | Q(requested_by_name__icontains=q)
                | Q(section_ward__icontains=q)
            )
        return list(qs[:200])

    documents = _safe_query(_load, None)
    db_ok = documents is not None
    documents = documents or []
    return render(request, "clinic/clinic_documents.html", {
        "documents": documents,
        "db_ok": db_ok,
        "q": q,
    })


@login_required
def ordering_document_detail(request, pk):
    """Read-only view of an archived ordering form (printable).

    The ESRF and the pre-printed ward forms (top-up, cleaning) are all stored
    as OrderingDocuments; the form's own layout is chosen from its form_type so
    each one renders with its real columns.
    """
    doc = get_object_or_404(models.OrderingDocument, pk=pk)
    fdef = order_form_defs.def_for_form_type(doc.form_type)
    if fdef:
        return render(request, "clinic/order_form_document.html", {
            "doc": doc, "form": fdef, "columns": fdef["columns"],
            "mailto": _order_mailto_link(doc, fdef),
            "is_sent": doc.status == models.OrderingDocument.STATUS_SENT,
        })
    return render(request, "clinic/ordering_document.html", {
        "doc": doc,
        "mailto": _mailto_link(doc),
        "is_sent": doc.status == models.OrderingDocument.STATUS_SENT,
    })


# ------------------------------------------------ pre-printed ward order forms


def _parse_order_items(request, fdef):
    """Pull the line-item arrays from POST into a clean list of dicts, keyed by
    the form's own columns. Rows with neither a code nor a description drop."""
    keys = [c["key"] for c in fdef["columns"]]
    lists = {k: request.POST.getlist(k) for k in keys}
    n = max((len(v) for v in lists.values()), default=0)
    rows = []
    for i in range(n):
        row = {k: (lists[k][i].strip() if i < len(lists[k]) else "") for k in keys}
        if not row.get("code") and not row.get("description"):
            continue
        rows.append(row)
    return rows


def _send_order_form_email(doc, fdef):
    """Render and send a ward ordering form to its processing office. Raises on
    failure so the caller can report it."""
    subject = f"{fdef['title']} — {doc.section_ward} ({doc.reference})"
    ctx = {"doc": doc, "form": fdef, "columns": fdef["columns"]}
    html_body = render_to_string("clinic/email/order_form.html", ctx)
    text_body = render_to_string("clinic/email/order_form.txt", ctx)
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[doc.recipient_email or fdef["recipient"]],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)


def _order_mailto_link(doc, fdef):
    """Fallback mailto: link so the user can send from their own client."""
    keys = [c["key"] for c in fdef["columns"]]
    lines = [fdef["title"], f"Reference: {doc.reference}",
             f"Section/Ward: {doc.section_ward}", f"Cost Centre: {doc.cost_centre}",
             f"Ext no.: {doc.ext_no or ''}"]
    if doc.delivery_period:
        lines.append(f"{fdef['note_label']}: {doc.delivery_period}")
    lines += ["", "Items:"]
    for it in (doc.items or []):
        if it.get("code") or it.get("description"):
            lines.append("  - " + "  ".join(str(it.get(k, "")) for k in keys if it.get(k, "")))
    lines += ["", f"Requested by: {doc.requested_by_name or ''}", f"Date: {doc.form_date or ''}"]
    body = "\r\n".join(lines)
    subject = f"{fdef['title']} — {doc.section_ward} ({doc.reference})"
    recipient = doc.recipient_email or fdef["recipient"]
    return (f"mailto:{recipient}?subject={urllib.parse.quote(subject)}"
            f"&body={urllib.parse.quote(body)}")


@login_required
def order_form(request, slug):
    """A fillable pre-printed ward ordering form (top-up / cleaning).

    GET renders the form with the pre-printed rows; POST saves it to Clinic
    Documents, files a copy in the Library, and emails it to the processing
    office (Disposables & Supplies).
    """
    fdef = order_form_defs.get_form_def(slug)
    if not fdef:
        raise Http404("Unknown ordering form.")
    if request.method == "POST":
        return _order_form_submit(request, fdef)
    return render(request, fdef["template"], {
        "form": fdef,
        "columns": fdef["columns"],
        "user_full_name": _user_full_name(request.user),
        "today": datetime.date.today(),
        "recipient": fdef["recipient"],
    })


def _order_form_submit(request, fdef):
    items = _parse_order_items(request, fdef)
    ctx_form = {
        "form": fdef, "columns": fdef["columns"],
        "user_full_name": _user_full_name(request.user),
        "today": datetime.date.today(), "recipient": fdef["recipient"],
    }
    if not items:
        messages.error(request, "Add at least one item before sending.")
        return render(request, fdef["template"], ctx_form)

    raw_date = (request.POST.get("form_date") or "").strip()
    try:
        form_date = datetime.date.fromisoformat(raw_date) if raw_date else datetime.date.today()
    except ValueError:
        form_date = datetime.date.today()

    doc = models.OrderingDocument(
        reference=_next_reference(fdef["ref_prefix"]),
        form_type=fdef["form_type"],
        section_ward=fdef["section_ward"],
        cost_centre=fdef["cost_centre"],
        ext_no=(request.POST.get("ext_no") or "").strip(),
        # The single free header note — "Team / Day" or "Remarks" per form.
        delivery_period=(request.POST.get("note") or "").strip(),
        items=items,
        requested_by_name=(request.POST.get("requested_by") or "").strip()
                          or _user_full_name(request.user),
        requested_by_username=request.user.get_username(),
        form_date=form_date,
        recipient_email=fdef["recipient"],
        status=models.OrderingDocument.STATUS_SAVED,
    )

    email_ok, email_note = False, ""
    if _email_configured():
        try:
            _send_order_form_email(doc, fdef)
            email_ok = True
        except Exception as exc:  # noqa: BLE001 — surface any send error to the user
            email_note = f"Email could not be sent ({exc}). The form was saved."
    else:
        email_note = ("Email sending isn't set up yet, so the form was saved to "
                      "Clinic Documents and the Library but not sent automatically.")

    if email_ok:
        doc.status = models.OrderingDocument.STATUS_SENT
        doc.sent_at = timezone.now()

    saved = True
    try:
        doc.save()
    except Exception:
        saved = False

    # Keep a copy of the actual form in the Library, exactly like the ESRF.
    if saved:
        _file_in_library(
            title=f"{fdef['title']} — {doc.reference}",
            category=models.LibraryDocument.CORRESPONDENCE
                     if email_ok else models.LibraryDocument.REQUISITION,
            source=models.LibraryDocument.SOURCE_REQUISITION,
            html=render_to_string("clinic/email/order_form.html",
                                  {"doc": doc, "form": fdef, "columns": fdef["columns"]}),
            reference=doc.reference,
            description=(f"Sent to {doc.recipient_email} on {timezone.now():%d/%m/%Y}."
                         if email_ok else "Prepared but not emailed."),
            by=request.user.get_username(),
        )

    if email_ok:
        messages.success(
            request,
            f"{fdef['title']} {doc.reference} sent to {doc.recipient_email}, and "
            f"saved to Clinic Documents and the Library.")
    elif saved:
        messages.warning(request, email_note)
    else:
        messages.error(
            request,
            "The database is unavailable, so the form could not be saved. "
            "Please try again shortly.")
        return redirect("clinic:order_form", slug=fdef["slug"])

    return redirect("clinic:ordering_document_detail", pk=doc.pk)


# ---------------------------------------------------------------- library


def _file_in_library(*, title, category, source, html, reference=None,
                     patient_id=None, description=None, by=None):
    """Save a generated document into the Library automatically.

    Used whenever the app produces something worth keeping — a requisition
    emailed to Logistics, a discharge letter, a closed tender. Failures are
    swallowed: filing a copy must never break the action that produced it.
    """
    try:
        stamp = timezone.now().strftime("%Y%m%d-%H%M%S")
        slug = re.sub(r"[^A-Za-z0-9]+", "-", (reference or title))[:60].strip("-")
        name = f"{slug or 'document'}-{stamp}.html"
        content = ContentFile(html.encode("utf-8"), name=name)
        doc = models.LibraryDocument(
            title=title,
            category=category,
            source=source,
            auto_filed=True,
            reference=reference,
            patient_id=patient_id,
            description=description,
            original_name=name,
            size_bytes=content.size,
            uploaded_by=by,
        )
        doc.file.save(name, content, save=False)
        with transaction.atomic():
            doc.save()
        return doc
    except Exception:
        return None


@login_required
def library(request):
    """The clinic Library: stored documents plus quick access to every
    document-producing tool on the platform."""
    if request.method == "POST":
        upload = request.FILES.get("file")
        title = (request.POST.get("title") or "").strip()
        if not upload:
            messages.error(request, "Choose a file to upload.")
        else:
            try:
                doc = models.LibraryDocument(
                    title=title or upload.name,
                    category=(request.POST.get("category") or models.LibraryDocument.OTHER),
                    description=(request.POST.get("description") or "").strip() or None,
                    file=upload,
                    original_name=upload.name,
                    size_bytes=getattr(upload, "size", 0) or 0,
                    uploaded_by=request.user.get_username(),
                )
                doc.save()
                messages.success(request, f"“{doc.title}” added to the Library.")
            except Exception:
                messages.error(request, "That file could not be saved. Please try again.")
        return redirect("clinic:library")

    q = (request.GET.get("q") or "").strip()
    cat = (request.GET.get("category") or "").strip()
    def _load():
        qs = models.LibraryDocument.objects.all()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
        if cat:
            qs = qs.filter(category=cat)
        return list(qs[:300])

    docs = _safe_query(_load, None)
    db_ok = docs is not None
    docs = docs or []

    return render(request, "clinic/library.html", {
        "documents": docs, "db_ok": db_ok, "q": q, "category": cat,
        "categories": models.LibraryDocument.CATEGORY_CHOICES,
    })


@login_required
def file_discharge_letter(request):
    """File a copy of a produced discharge letter in the Library.

    Called by the letter page when it is printed or saved as a PDF — that is
    the moment the letter actually exists, so a copy is kept automatically.
    """
    if request.method != "POST":
        return JsonResponse({"ok": False}, status=405)
    html = request.POST.get("html") or ""
    if not html.strip():
        return JsonResponse({"ok": False, "error": "empty"}, status=400)

    name = (request.POST.get("patient_name") or "").strip()
    pid = (request.POST.get("patient_id") or "").strip() or None
    doc = _file_in_library(
        title=f"Discharge letter — {name}" if name else "Discharge letter",
        category=models.LibraryDocument.DISCHARGE_LETTER,
        source=models.LibraryDocument.SOURCE_DISCHARGE,
        html=html,
        reference=(request.POST.get("id_card") or "").strip() or None,
        patient_id=pid,
        description=f"Produced on {timezone.now():%d/%m/%Y}.",
        by=request.user.get_username(),
    )
    return JsonResponse({"ok": bool(doc), "id": str(doc.id) if doc else None})


@login_required
def library_file(request, pk):
    """Serve a stored document (inline for PDFs/images, else download)."""
    doc = get_object_or_404(models.LibraryDocument, pk=pk)
    try:
        fh = doc.file.open("rb")
    except Exception:
        raise Http404("File is no longer available.")
    inline = doc.extension in {"pdf", "png", "jpg", "jpeg", "gif", "webp", "svg", "txt"}
    response = FileResponse(fh, as_attachment=not inline,
                            filename=doc.original_name or doc.file.name.rsplit("/", 1)[-1])
    return response


@login_required
def library_delete(request, pk):
    if request.method != "POST":
        return redirect("clinic:library")
    doc = get_object_or_404(models.LibraryDocument, pk=pk)
    title = doc.title
    try:
        doc.file.delete(save=False)
    except Exception:
        pass
    try:
        doc.delete()
        messages.success(request, f"“{title}” removed from the Library.")
    except Exception:
        messages.error(request, "Could not remove that document.")
    return redirect("clinic:library")


def _parse_iso_date(raw):
    """Parse a YYYY-MM-DD string into a date, or None."""
    try:
        return datetime.date.fromisoformat((raw or "").strip())
    except ValueError:
        return None


@login_required
def diary(request):
    """Diary — a running log of dated entries. GET lists, POST adds one."""
    D = models.DiaryEntry
    if request.method == "POST":
        body = (request.POST.get("body") or "").strip()
        if not body:
            messages.error(request, "Write something for the diary entry.")
        else:
            try:
                D.objects.create(
                    entry_date=_parse_iso_date(request.POST.get("entry_date")) or datetime.date.today(),
                    title=(request.POST.get("title") or "").strip() or None,
                    body=body,
                    created_by=request.user.get_username(),
                )
                messages.success(request, "Diary entry added.")
            except Exception:
                messages.error(request, "Could not save — the database is unavailable.")
        return redirect("clinic:diary")

    entries = _safe_query(lambda: list(D.objects.all()), None)
    db_ok = entries is not None
    return render(request, "clinic/diary.html", {
        "entries": entries or [],
        "db_ok": db_ok,
        "today": datetime.date.today(),
    })


@login_required
def diary_entry_edit(request, pk):
    """Update a diary entry (POST only)."""
    if request.method != "POST":
        return redirect("clinic:diary")
    entry = get_object_or_404(models.DiaryEntry, pk=pk)
    body = (request.POST.get("body") or "").strip()
    if not body:
        messages.error(request, "A diary entry can't be empty.")
        return redirect("clinic:diary")
    entry.body = body
    entry.title = (request.POST.get("title") or "").strip() or None
    ed = _parse_iso_date(request.POST.get("entry_date"))
    if ed:
        entry.entry_date = ed
    try:
        entry.save()
        messages.success(request, "Diary entry updated.")
    except Exception:
        messages.error(request, "Could not update — the database is unavailable.")
    return redirect("clinic:diary")


@login_required
def diary_entry_delete(request, pk):
    """Delete a diary entry (POST only)."""
    if request.method != "POST":
        return redirect("clinic:diary")
    entry = get_object_or_404(models.DiaryEntry, pk=pk)
    try:
        entry.delete()
        messages.success(request, "Diary entry removed.")
    except Exception:
        messages.error(request, "Could not remove that entry.")
    return redirect("clinic:diary")


# ----------------------------------------------------------------- admin / users


def _is_admin(user):
    """Only active superusers may manage other users."""
    return bool(user.is_active and user.is_superuser)


@login_required
def admin_users(request):
    """Admin hub.

    * Roster staff (add / remove core and overtime staff) — available to any
      signed-in user, moved here from the Roster page.
    * Users & passwords — superusers only: add users and set their name,
      surname, email and password. A user's Name/Surname here feed the officer
      fields on every form, which is what drives the name automation.
    """
    User = get_user_model()
    is_admin = _is_admin(request.user)

    if request.method == "POST" and (request.POST.get("action") == "create"):
        # New users log in with their email, so the email is stored as the
        # username too. Name/Surname feed the officer fields on every form.
        email = (request.POST.get("email") or "").strip()
        first = (request.POST.get("first_name") or "").strip()
        last = (request.POST.get("last_name") or "").strip()
        password = request.POST.get("password") or ""
        if not email or "@" not in email:
            messages.error(request, "Enter the user's login email.")
        elif len(password) < 8:
            messages.error(request, "The temporary password must be at least 8 characters.")
        elif User.objects.filter(username__iexact=email).exists() or User.objects.filter(email__iexact=email).exists():
            messages.error(request, f"A user with email “{email}” already exists.")
        else:
            try:
                u = User(username=email, first_name=first, last_name=last,
                         email=email, is_active=True, is_staff=False, is_superuser=False)
                u.set_password(password)
                u.save()
                messages.success(request, f"User “{email}” created with a temporary password.")
            except Exception:
                messages.error(request, "Could not create the user — please try again.")
        return redirect("clinic:admin_users")

    RS = models.RosterStaff
    core_staff = _safe_query(
        lambda: list(RS.objects.filter(category=RS.CORE).order_by("display_order", "full_name")), []) or []
    ot_staff = _safe_query(
        lambda: list(RS.objects.filter(category=RS.OVERTIME).order_by("display_order", "full_name")), []) or []

    users = _safe_query(lambda: list(User.objects.order_by("username")), []) or []
    return render(request, "clinic/admin_users.html", {
        "users": users,
        "is_admin": is_admin,
        "core_staff": core_staff,
        "ot_staff": ot_staff,
    })


@login_required
def admin_user_edit(request, pk):
    """Update a user's name, surname and email, and optionally reset their
    password or toggle whether the account is active (POST only).

    Editable by any signed-in user, except that changing an administrator's
    account requires being an administrator.
    """
    if request.method != "POST":
        return redirect("clinic:admin_users")
    User = get_user_model()
    u = get_object_or_404(User, pk=pk)
    if u.is_superuser and not _is_admin(request.user):
        messages.error(request, "Only an administrator can edit an administrator's account.")
        return redirect("clinic:admin_users")

    u.first_name = (request.POST.get("first_name") or "").strip()
    u.last_name = (request.POST.get("last_name") or "").strip()
    u.email = (request.POST.get("email") or "").strip()

    new_password = request.POST.get("password") or ""
    if new_password:
        if len(new_password) < 8:
            messages.error(request, "The new password must be at least 8 characters.")
            return redirect("clinic:admin_users")
        u.set_password(new_password)

    # Allow deactivating an account, but never let an admin lock themselves out.
    want_active = bool(request.POST.get("is_active"))
    if u.pk == request.user.pk and not want_active:
        messages.error(request, "You can't deactivate your own account.")
        return redirect("clinic:admin_users")
    u.is_active = want_active

    try:
        u.save()
        note = "password reset and " if new_password else ""
        messages.success(request, f"User “{u.get_username()}” updated ({note}details saved).")
    except Exception:
        messages.error(request, "Could not update the user — please try again.")
    return redirect("clinic:admin_users")


@login_required
def admin_password_self(request):
    """Change the signed-in account's own password (POST only)."""
    if request.method != "POST":
        return redirect("clinic:admin_users")
    pw = request.POST.get("password") or ""
    pw2 = request.POST.get("password2") or ""
    if len(pw) < 8:
        messages.error(request, "Your new password must be at least 8 characters.")
    elif pw != pw2:
        messages.error(request, "The two passwords don't match.")
    else:
        try:
            u = request.user
            u.set_password(pw)
            u.save()
            # Keep this session signed in after the password change.
            update_session_auth_hash(request, u)
            messages.success(request, "Your password has been changed.")
        except Exception:
            messages.error(request, "Could not change your password — please try again.")
    return redirect("clinic:admin_users")


@login_required
def admin_password_set(request, pk):
    """Set a new password for another user (POST only).

    Anyone signed in can reset an ordinary user's password; changing an
    administrator's password requires being an administrator, so a shared
    account can't take over an admin login.
    """
    if request.method != "POST":
        return redirect("clinic:admin_users")
    User = get_user_model()
    u = get_object_or_404(User, pk=pk)
    if u.is_superuser and not _is_admin(request.user):
        messages.error(request, "Only an administrator can change an administrator's password.")
        return redirect("clinic:admin_users")
    pw = request.POST.get("password") or ""
    if len(pw) < 8:
        messages.error(request, "The new password must be at least 8 characters.")
        return redirect("clinic:admin_users")
    try:
        u.set_password(pw)
        u.save()
        if u.pk == request.user.pk:
            update_session_auth_hash(request, u)
        messages.success(request, f"Password changed for {u.email or u.get_username()}.")
    except Exception:
        messages.error(request, "Could not change that password — please try again.")
    return redirect("clinic:admin_users")


@login_required
def cpsu(request):
    """CPSU (Central Procurement & Supplies Unit) landing page."""
    return render(request, "clinic/cpsu.html")


def _tender_summary(data):
    """Derive (title, bidder_count, lowest_bid, lowest_bidder) from editor state."""
    header = (data or {}).get("header") or {}
    title = (header.get("title") or "").strip() or "Untitled tender"
    bidders = (data or {}).get("bidders") or []
    low_val, low_name = None, None
    for b in bidders:
        try:
            v = float(str(b.get("bid")).strip())
        except (TypeError, ValueError):
            continue
        if low_val is None or v < low_val:
            low_val, low_name = v, (b.get("supplier") or "").strip()
    return title, len(bidders), low_val, low_name


@login_required
def cpsu_tenders(request):
    """Tenders hub — New Tender / Current Tenders / Closed Tenders."""
    T = models.TenderEvaluation
    counts = _safe_query(
        lambda: (T.objects.filter(status=T.STATUS_OPEN).count(),
                 T.objects.filter(status=T.STATUS_CLOSED).count()), None)
    db_ok = counts is not None
    open_count, closed_count = counts if counts else (None, None)
    return render(request, "clinic/cpsu_tenders.html", {
        "open_count": open_count, "closed_count": closed_count, "db_ok": db_ok,
    })


def _tender_list(request, status, title):
    tenders = _safe_query(
        lambda: list(models.TenderEvaluation.objects.filter(status=status)[:300]), None)
    db_ok = tenders is not None
    tenders = tenders or []
    return render(request, "clinic/tender_list.html", {
        "tenders": tenders, "db_ok": db_ok, "status": status, "title": title,
        "is_closed": status == models.TenderEvaluation.STATUS_CLOSED,
    })


@login_required
def tenders_current(request):
    """List of open (current) tenders."""
    return _tender_list(request, models.TenderEvaluation.STATUS_OPEN, "Current Tenders")


@login_required
def tenders_closed(request):
    """List of closed tenders."""
    return _tender_list(request, models.TenderEvaluation.STATUS_CLOSED, "Closed Tenders")


@login_required
def tender_new(request):
    """Create a blank tender and open its editor."""
    t = models.TenderEvaluation(
        title="Untitled tender",
        created_by_username=request.user.get_username(),
        data={"header": {}, "bidders": [], "selectedId": None},
    )
    try:
        t.save()
    except Exception:
        messages.error(request, "Could not create a tender — the database is unavailable.")
        return redirect("clinic:cpsu_tenders")
    return redirect("clinic:tender_edit", pk=t.pk)


@login_required
def tender_edit(request, pk):
    """Open a tender's editor (GET) or save it (POST)."""
    tender = get_object_or_404(models.TenderEvaluation, pk=pk)
    if request.method == "POST":
        return _tender_save(request, tender)
    default = {"header": {}, "bidders": [], "selectedId": None}
    return render(request, "clinic/cpsu_tender_edit.html", {
        "tender": tender,
        "data_json": json.dumps(tender.data or default),
    })


def _tender_save(request, tender):
    action = (request.POST.get("action") or "save").strip()

    if action == "reopen":
        tender.status = models.TenderEvaluation.STATUS_OPEN
        try:
            tender.save(update_fields=["status", "updated_at"])
            messages.success(request, "Tender reopened.")
        except Exception:
            messages.error(request, "Could not reopen the tender.")
        return redirect("clinic:tender_edit", pk=tender.pk)

    try:
        data = json.loads(request.POST.get("payload") or "{}")
        if not isinstance(data, dict):
            data = {}
    except (ValueError, TypeError):
        data = {}
    data.setdefault("header", {})
    data.setdefault("bidders", [])

    title, count, low_val, low_name = _tender_summary(data)
    tender.data = data
    tender.title = title
    tender.bidder_count = count
    tender.lowest_bid = low_val
    tender.lowest_bidder = low_name
    if action == "close":
        tender.status = models.TenderEvaluation.STATUS_CLOSED

    try:
        tender.save()
    except Exception:
        messages.error(request, "Could not save — the database is unavailable.")
        return redirect("clinic:tender_edit", pk=tender.pk)

    if action == "close":
        # Keep a copy of the completed evaluation in the Library.
        _file_in_library(
            title=f"Tender evaluation — {tender.title}",
            category=models.LibraryDocument.TENDER,
            source=models.LibraryDocument.SOURCE_TENDER,
            html=render_to_string("clinic/tender_summary.html", {"t": tender}),
            reference=tender.title,
            description=(f"{tender.bidder_count} bidder(s)."
                         + (f" Lowest €{tender.lowest_bid:.2f}"
                            f"{' — ' + tender.lowest_bidder if tender.lowest_bidder else ''}."
                            if tender.lowest_bid is not None else "")),
            by=request.user.get_username(),
        )
        messages.success(
            request, f"Tender “{tender.title}” closed, saved and filed in the Library.")
        return redirect("clinic:cpsu_tenders")
    messages.success(request, "Tender saved.")
    return redirect("clinic:tender_edit", pk=tender.pk)


@login_required
def tender_delete(request, pk):
    """Delete a tender (POST only)."""
    if request.method != "POST":
        return redirect("clinic:cpsu_tenders")
    tender = get_object_or_404(models.TenderEvaluation, pk=pk)
    try:
        tender.delete()
        messages.success(request, "Tender deleted.")
    except Exception:
        messages.error(request, "Could not delete the tender.")
    return redirect("clinic:cpsu_tenders")


# ----------------------------------------------------- CPSU product catalogue


@login_required
def cpsu_appliances(request):
    """Appliance & Accessories catalogue — list, search and add products."""
    A = models.ApplianceCatalogueItem
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        if not name:
            messages.error(request, "Give the product a name.")
        else:
            try:
                A.objects.create(
                    item_type=(request.POST.get("item_type") or A.APPLIANCE),
                    name=name,
                    brand=(request.POST.get("brand") or "").strip() or None,
                    product_code=(request.POST.get("product_code") or "").strip() or None,
                    category=(request.POST.get("category") or "").strip() or None,
                    size=(request.POST.get("size") or "").strip() or None,
                    description=(request.POST.get("description") or "").strip() or None,
                    on_contract=bool(request.POST.get("on_contract")),
                    created_by_username=request.user.get_username(),
                )
                messages.success(request, f"“{name}” added to the catalogue.")
            except Exception:
                messages.error(request, "Could not save — the database is unavailable.")
        return redirect("clinic:cpsu_appliances")

    q = (request.GET.get("q") or "").strip()
    kind = (request.GET.get("type") or "").strip()

    def _load():
        qs = A.objects.all()
        if q:
            qs = qs.filter(
                Q(name__icontains=q) | Q(brand__icontains=q)
                | Q(product_code__icontains=q) | Q(category__icontains=q))
        if kind in (A.APPLIANCE, A.ACCESSORY):
            qs = qs.filter(item_type=kind)
        return list(qs[:400])

    items = _safe_query(_load, None)
    db_ok = items is not None
    items = items or []
    return render(request, "clinic/cpsu_appliances.html", {
        "items": items, "db_ok": db_ok, "q": q, "type": kind,
        "types": A.TYPE_CHOICES,
    })


@login_required
def cpsu_appliance_delete(request, pk):
    """Remove a catalogue item (POST only)."""
    if request.method != "POST":
        return redirect("clinic:cpsu_appliances")
    item = get_object_or_404(models.ApplianceCatalogueItem, pk=pk)
    name = item.name
    try:
        item.delete()
        messages.success(request, f"“{name}” removed from the catalogue.")
    except Exception:
        messages.error(request, "Could not remove that item.")
    return redirect("clinic:cpsu_appliances")


@login_required
def cpsu_specifications(request):
    """Product specifications register — list, search and add specs."""
    S = models.ProductSpecification
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        if not title:
            messages.error(request, "Give the specification a title.")
        else:
            try:
                S.objects.create(
                    title=title,
                    product_group=(request.POST.get("product_group") or "").strip() or None,
                    reference=(request.POST.get("reference") or "").strip() or None,
                    specification=(request.POST.get("specification") or "").strip() or None,
                    mandatory=bool(request.POST.get("mandatory")),
                    created_by_username=request.user.get_username(),
                )
                messages.success(request, f"Specification “{title}” added.")
            except Exception:
                messages.error(request, "Could not save — the database is unavailable.")
        return redirect("clinic:cpsu_specifications")

    q = (request.GET.get("q") or "").strip()

    def _load():
        qs = S.objects.all()
        if q:
            qs = qs.filter(
                Q(title__icontains=q) | Q(product_group__icontains=q)
                | Q(reference__icontains=q) | Q(specification__icontains=q))
        return list(qs[:400])

    specs = _safe_query(_load, None)
    db_ok = specs is not None
    specs = specs or []
    return render(request, "clinic/cpsu_specifications.html", {
        "specs": specs, "db_ok": db_ok, "q": q,
    })


@login_required
def cpsu_specification_delete(request, pk):
    """Remove a specification (POST only)."""
    if request.method != "POST":
        return redirect("clinic:cpsu_specifications")
    spec = get_object_or_404(models.ProductSpecification, pk=pk)
    title = spec.title
    try:
        spec.delete()
        messages.success(request, f"Specification “{title}” removed.")
    except Exception:
        messages.error(request, "Could not remove that specification.")
    return redirect("clinic:cpsu_specifications")


# ----------------------------------------------------------------- reminders


def _reminders_due_today():
    """Active reminders that fire today — for the dashboard. DB-safe (None on error)."""
    today = datetime.date.today()
    return _safe_query(
        lambda: [r for r in models.Reminder.objects.filter(active=True) if r.is_due_on(today)],
        None,
    )


# Curated destinations a reminder can link to. Each is (label, url-name); the
# label doubles as the call-to-action shown on the reminder card and home page.
# Only these internal URLs are accepted when saving, so a reminder can never
# link somewhere arbitrary or off-site.
_REMINDER_ACTION_TARGETS = [
    ("Ordering Forms", "clinic:ordering_forms"),
    ("Requisition Form (ESRF)", "clinic:esrf_form"),
    ("Clinic Documents", "clinic:clinic_documents"),
    ("Appointments", "clinic:appointments"),
    ("Inpatient Visits", "clinic:ward"),
    ("Patients", "clinic:patient_list"),
    ("Discharge Letter", "clinic:discharge_letter"),
    ("CPSU", "clinic:cpsu"),
    ("Library", "clinic:library"),
    ("Roster", "clinic:roster"),
    ("Reports", "clinic:reports"),
]


def _reminder_action_choices():
    """Resolved (label, url) pairs for the reminder 'Opens' dropdown."""
    out = []
    for label, name in _REMINDER_ACTION_TARGETS:
        try:
            out.append((label, reverse(name)))
        except Exception:
            pass
    return out


def _parse_reminder_form(request):
    """Turn the POST into reminder fields, or None if there's no title."""
    R = models.Reminder
    title = (request.POST.get("title") or "").strip()
    if not title:
        return None
    freq = (request.POST.get("frequency") or R.WEEKLY).strip()
    if freq not in dict(R.FREQUENCY_CHOICES):
        freq = R.WEEKLY

    def _int(name):
        try:
            return int(request.POST.get(name))
        except (TypeError, ValueError):
            return None

    on_date = None
    if freq == R.ONCE:
        try:
            on_date = datetime.date.fromisoformat((request.POST.get("on_date") or "").strip())
        except ValueError:
            on_date = None
    at_time = None
    raw_time = (request.POST.get("at_time") or "").strip()
    if raw_time:
        try:
            at_time = datetime.time.fromisoformat(raw_time)
        except ValueError:
            at_time = None

    # Optional call-to-action: accept only one of the curated internal targets,
    # and derive its label from that same list so the card link is consistent.
    action_url = (request.POST.get("action_url") or "").strip()
    action_label = None
    if action_url:
        allowed = {url: label for label, url in _reminder_action_choices()}
        if action_url in allowed:
            action_label = allowed[action_url]
        else:
            action_url = None

    return {
        "title": title,
        "message": (request.POST.get("message") or "").strip() or None,
        "recipient_email": (request.POST.get("recipient_email") or "").strip() or None,
        "frequency": freq,
        "weekday": _int("weekday") if freq == R.WEEKLY else None,
        "day_of_month": _int("day_of_month") if freq == R.MONTHLY else None,
        "on_date": on_date,
        "at_time": at_time,
        "action_url": action_url,
        "action_label": action_label,
    }


@login_required
def reminders(request):
    """Reminders: a list of reminders, when each fires, a repeat (on/off)
    toggle, who it's emailed to, and its timing."""
    R = models.Reminder
    if request.method == "POST":
        fields = _parse_reminder_form(request)
        if not fields:
            messages.error(request, "Give the reminder a title.")
        else:
            try:
                R.objects.create(created_by=request.user.get_username(), **fields)
                messages.success(request, f"Reminder “{fields['title']}” added.")
            except Exception:
                messages.error(request, "Could not save — the database is unavailable.")
        return redirect("clinic:reminders")

    items = _safe_query(lambda: list(R.objects.all()), None)
    db_ok = items is not None
    items = items or []
    today = datetime.date.today()
    return render(request, "clinic/reminders.html", {
        "reminders": items,
        "db_ok": db_ok,
        "due_today": [r for r in items if r.is_due_on(today)],
        "frequencies": R.FREQUENCY_CHOICES,
        "weekdays": R.WEEKDAYS,
        "action_choices": _reminder_action_choices(),
        "email_ready": _email_configured(),
    })


@login_required
def reminder_toggle(request, pk):
    """Flip a reminder's repeat switch on or off (POST only)."""
    if request.method != "POST":
        return redirect("clinic:reminders")
    r = get_object_or_404(models.Reminder, pk=pk)
    r.active = not r.active
    try:
        r.save(update_fields=["active"])
        messages.success(request, f"“{r.title}” {'repeating' if r.active else 'paused'}.")
    except Exception:
        messages.error(request, "Could not update that reminder.")
    return redirect("clinic:reminders")


@login_required
def reminder_delete(request, pk):
    """Delete a reminder (POST only)."""
    if request.method != "POST":
        return redirect("clinic:reminders")
    r = get_object_or_404(models.Reminder, pk=pk)
    title = r.title
    try:
        r.delete()
        messages.success(request, f"“{title}” removed.")
    except Exception:
        messages.error(request, "Could not remove that reminder.")
    return redirect("clinic:reminders")


def _send_reminder_email(reminder):
    """Email a single reminder to its recipient. Raises on failure."""
    ctx = {"r": reminder, "today": datetime.date.today()}
    html_body = render_to_string("clinic/email/reminder.html", ctx)
    text_body = render_to_string("clinic/email/reminder.txt", ctx)
    msg = EmailMultiAlternatives(
        subject=f"Reminder: {reminder.title}",
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[reminder.recipient_email],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)


@login_required
def reminder_send(request, pk):
    """Send a reminder's email right now (POST only)."""
    if request.method != "POST":
        return redirect("clinic:reminders")
    r = get_object_or_404(models.Reminder, pk=pk)
    if not r.recipient_email:
        messages.error(request, f"“{r.title}” has no recipient email to send to.")
    elif not _email_configured():
        messages.warning(request, "Email sending isn't set up on the server yet, so "
                                  "this reminder can't be emailed automatically.")
    else:
        try:
            _send_reminder_email(r)
            r.last_sent_at = timezone.now()
            r.save(update_fields=["last_sent_at"])
            messages.success(request, f"Reminder emailed to {r.recipient_email}.")
        except Exception as exc:  # noqa: BLE001 — surface the send error
            messages.error(request, f"Could not send ({exc}).")
    return redirect("clinic:reminders")


# -------------------------------------------------------------- roster / shifts


# The shift codes shown in the roster legend, with their colours.
ROSTER_CODES = [
    {"code": "D", "label": "Day", "bg": "#1f2937", "fg": "#ffffff"},
    {"code": "AM", "label": "Morning", "bg": "#0891b2", "fg": "#ffffff"},
    {"code": "R", "label": "Rest/Off", "bg": "#e5e7eb", "fg": "#111827"},
    {"code": "S", "label": "Sick", "bg": "#ef4444", "fg": "#ffffff"},
    {"code": "M", "label": "Maternity", "bg": "#db2777", "fg": "#ffffff"},
    {"code": "St", "label": "Study", "bg": "#3b82f6", "fg": "#ffffff"},
    {"code": "OT", "label": "Overtime", "bg": "#f59e0b", "fg": "#111827"},
    {"code": "L", "label": "Annual Leave", "bg": "#16a34a", "fg": "#ffffff"},
    {"code": "TOL", "label": "TIL Off", "bg": "#7c3aed", "fg": "#ffffff"},
    {"code": "TIL", "label": "TIL In", "bg": "#0d9488", "fg": "#ffffff"},
    {"code": "COD-in", "label": "Change of duty in", "bg": "#0ea5e9", "fg": "#ffffff"},
    {"code": "COD-off", "label": "Change of duty off", "bg": "#92400e", "fg": "#ffffff"},
]
ROSTER_CODE_MAP = {c["code"]: c for c in ROSTER_CODES}


def _roster_redirect(request):
    """Back to where the staff change was made — the Admin page when the form
    came from there, otherwise the roster (keeping the month being viewed)."""
    if (request.POST.get("back") or "").strip() == "admin":
        return reverse("clinic:admin_users")
    y, m = request.POST.get("year"), request.POST.get("month")
    base = reverse("clinic:roster")
    return f"{base}?year={y}&month={m}" if (y and m) else base


def _easter_sunday(year):
    """Western (Gregorian) Easter Sunday — anonymous Gregorian algorithm."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return datetime.date(year, month, day)


def maltese_public_holidays(year):
    """{date: full name} for Malta's national and public holidays in ``year``.

    Fixed-date feasts plus the one movable holiday, Good Friday (Easter − 2).
    """
    d = datetime.date
    good_friday = _easter_sunday(year) - datetime.timedelta(days=2)
    return {
        d(year, 1, 1): "New Year's Day",
        d(year, 2, 10): "Feast of St Paul's Shipwreck",
        d(year, 3, 19): "Feast of St Joseph",
        d(year, 3, 31): "Freedom Day (Jum il-Ħelsien)",
        good_friday: "Good Friday",
        d(year, 5, 1): "Workers' Day (Jum il-Ħaddiem)",
        d(year, 6, 7): "Sette Giugno",
        d(year, 6, 29): "Feast of St Peter & St Paul (L-Imnarja)",
        d(year, 8, 15): "Feast of the Assumption (Santa Marija)",
        d(year, 9, 8): "Victory Day (Jum il-Vitorja)",
        d(year, 9, 21): "Independence Day (Jum l-Indipendenza)",
        d(year, 12, 8): "Feast of the Immaculate Conception",
        d(year, 12, 13): "Republic Day (Jum ir-Repubblika)",
        d(year, 12, 25): "Christmas Day",
    }


@login_required
def roster(request):
    """Monthly roster grid — staff down the side, days across the top, a shift
    code in each cell."""
    today = datetime.date.today()
    try:
        year = int(request.GET.get("year") or today.year)
        month = int(request.GET.get("month") or today.month)
        datetime.date(year, month, 1)
    except (ValueError, TypeError):
        year, month = today.year, today.month

    ndays = calendar.monthrange(year, month)[1]
    holidays = maltese_public_holidays(year)
    days = []
    for d in range(1, ndays + 1):
        dt = datetime.date(year, month, d)
        days.append({"day": d, "date": dt.isoformat(), "wd": dt.strftime("%a"),
                     "weekend": dt.weekday() >= 5, "sun": dt.weekday() == 6,
                     "holiday": holidays.get(dt), "today": dt == today})

    def _load():
        staff = list(models.RosterStaff.objects.filter(active=True))
        first, last = datetime.date(year, month, 1), datetime.date(year, month, ndays)
        smap = {}
        for sh in models.RosterShift.objects.filter(date__gte=first, date__lte=last):
            smap[(sh.staff_id, sh.date.day)] = sh.code
        return staff, smap

    loaded = _safe_query(_load, None)
    db_ok = loaded is not None
    staff, smap = loaded if loaded else ([], {})

    def build_rows(category):
        rows = []
        for st in staff:
            if st.category != category:
                continue
            cells = [{
                "date": datetime.date(year, month, d).isoformat(),
                "code": smap.get((st.id, d), ""),
                "meta": ROSTER_CODE_MAP.get(smap.get((st.id, d))),
                "sun": datetime.date(year, month, d).weekday() == 6,
                "holiday": bool(holidays.get(datetime.date(year, month, d))),
            } for d in range(1, ndays + 1)]
            rows.append({"staff": st, "cells": cells})
        return rows

    prev_m = datetime.date(year, month, 1) - datetime.timedelta(days=1)
    next_m = datetime.date(year, month, ndays) + datetime.timedelta(days=1)
    return render(request, "clinic/roster.html", {
        "year": year, "month": month,
        "month_label": datetime.date(year, month, 1).strftime("%B %Y"),
        "days": days,
        "month_holidays": [
            {"day": dt.day, "wd": dt.strftime("%a"), "name": name}
            for dt, name in sorted(holidays.items()) if dt.month == month
        ],
        "core_rows": build_rows(models.RosterStaff.CORE),
        "ot_rows": build_rows(models.RosterStaff.OVERTIME),
        "codes": ROSTER_CODES,
        "db_ok": db_ok,
        "prev": {"year": prev_m.year, "month": prev_m.month},
        "next": {"year": next_m.year, "month": next_m.month},
        "today": {"year": today.year, "month": today.month},
        "categories": models.RosterStaff.CATEGORY_CHOICES,
    })


@login_required
def roster_staff_add(request):
    """Add a person to the roster (POST)."""
    if request.method == "POST":
        name = (request.POST.get("full_name") or "").strip()
        if not name:
            messages.error(request, "Enter a name.")
        else:
            cat = request.POST.get("category")
            if cat not in dict(models.RosterStaff.CATEGORY_CHOICES):
                cat = models.RosterStaff.CORE
            try:
                order = _safe_count(models.RosterStaff.objects.filter(category=cat)) or 0
                st = models.RosterStaff.objects.create(
                    full_name=name,
                    role=(request.POST.get("role") or "").strip() or None,
                    category=cat, display_order=order)
                applied = _apply_shift_pattern(request, st)
                if applied:
                    messages.success(request, f"{name} added, with {applied} shifts from the pattern.")
                else:
                    messages.success(request, f"{name} added to the roster.")
            except Exception:
                messages.error(request, "Could not add — the database is unavailable.")
    return redirect(_roster_redirect(request))


def _apply_shift_pattern(request, staff):
    """Apply a repeating shift pattern from the add-staff form, if present.

    Reads the ``pattern`` cycle (a list of shift codes: D=Day, R=Off, AM=Morning)
    and ``pattern_start`` date, then fills each day from the start through the
    end of the following month by cycling the pattern. Returns the number of
    days filled (0 if no pattern was given).
    """
    cycle = [c for c in request.POST.getlist("pattern") if c in ROSTER_CODE_MAP]
    raw = (request.POST.get("pattern_start") or "").strip()
    try:
        start = datetime.date.fromisoformat(raw) if raw else None
    except ValueError:
        start = None
    if not cycle or not start:
        return 0
    # Horizon: the end of the month after the start month.
    ny, nm = (start.year + 1, 1) if start.month == 12 else (start.year, start.month + 1)
    horizon = datetime.date(ny, nm, calendar.monthrange(ny, nm)[1])
    d, i, n = start, 0, 0
    while d <= horizon:
        try:
            models.RosterShift.objects.update_or_create(
                staff=staff, date=d, defaults={"code": cycle[i % len(cycle)]})
            n += 1
        except Exception:
            pass
        d += datetime.timedelta(days=1)
        i += 1
    return n


@login_required
def roster_staff_delete(request, pk):
    """Remove a person (and their shifts) from the roster (POST)."""
    if request.method == "POST":
        st = get_object_or_404(models.RosterStaff, pk=pk)
        name = st.full_name
        try:
            st.delete()
            messages.success(request, f"{name} removed from the roster.")
        except Exception:
            messages.error(request, "Could not remove that person.")
    return redirect(_roster_redirect(request))


@login_required
def roster_shift_set(request):
    """Set or clear one cell's shift code. Returns JSON for the click UI."""
    if request.method != "POST":
        return JsonResponse({"ok": False}, status=405)
    try:
        d = datetime.date.fromisoformat((request.POST.get("date") or "").strip())
    except (ValueError, TypeError):
        return JsonResponse({"ok": False, "error": "bad date"}, status=400)
    st = get_object_or_404(models.RosterStaff, pk=request.POST.get("staff_id"))
    code = (request.POST.get("code") or "").strip()
    try:
        if not code:
            models.RosterShift.objects.filter(staff=st, date=d).delete()
            return JsonResponse({"ok": True, "code": "", "bg": "", "fg": ""})
        if code not in ROSTER_CODE_MAP:
            return JsonResponse({"ok": False, "error": "bad code"}, status=400)
        models.RosterShift.objects.update_or_create(
            staff=st, date=d, defaults={"code": code})
        meta = ROSTER_CODE_MAP[code]
        return JsonResponse({"ok": True, "code": code, "bg": meta["bg"], "fg": meta["fg"]})
    except Exception:
        return JsonResponse({"ok": False, "error": "db"}, status=500)


# ------------------------------------------------------------------ pathways


def _parse_date(value, default=None):
    try:
        return datetime.date.fromisoformat((value or "").strip())
    except ValueError:
        return default


def _pathway_stage_label(p):
    """Short human summary of what happens next on this pathway."""
    P = models.CarePathway
    if p.status == P.SITING_SCHEDULED:
        return "Awaiting stoma siting session"
    if p.status == P.AWAITING_SURGERY:
        return "Siting done — awaiting surgery"
    if p.status == P.INPATIENT:
        return "Inpatient — reviewing daily until discharge"
    if p.status == P.OUTPATIENT:
        return "Outpatient — seen by appointment"
    if p.status == P.DISCHARGED:
        return "Discharged"
    if p.status == P.FOLLOWUP:
        return "Old stoma — on follow-up"
    return "Closed"


@login_required
def pathway_detail(request, pk):
    """A pathway's timeline, with the actions available at its current stage."""
    pathway = get_object_or_404(models.CarePathway, pk=pk)
    if request.method == "POST":
        return _pathway_action(request, pathway)

    events = list(pathway.events.all()[:200])
    appts = list(pathway.followup_appointments.all()[:50])
    return render(request, "clinic/pathway_detail.html", {
        "p": pathway,
        "events": events,
        "appointments": appts,
        "stage_label": _pathway_stage_label(pathway),
        "today": datetime.date.today(),
    })


def _pathway_action(request, p):
    """Handle a stage action posted from the pathway detail page."""
    P = models.CarePathway
    E = models.PathwayEvent
    action = (request.POST.get("action") or "").strip()
    who = request.user.get_username()
    today = datetime.date.today()

    try:
        if action == "schedule_siting":
            d = _parse_date(request.POST.get("siting_scheduled_date"))
            if not d:
                messages.error(request, "Enter a valid siting date.")
            else:
                was = p.siting_scheduled_date
                p.siting_scheduled_date = d
                if p.status in {P.SITING_SCHEDULED, P.AWAITING_SURGERY}:
                    p.status = P.SITING_SCHEDULED
                p.save()
                messages.success(
                    request,
                    f"Siting session rescheduled to {d:%d/%m/%Y}." if was
                    else f"Siting session scheduled for {d:%d/%m/%Y}.",
                )

        elif action == "complete_siting":
            d = _parse_date(request.POST.get("siting_done_date"), today)
            p.siting_done_date = d
            p.siting_chart = {
                "stoma_type": (request.POST.get("chart_stoma_type") or "").strip(),
                "site_marked": (request.POST.get("chart_site_marked") or "").strip(),
                "abdomen": (request.POST.get("chart_abdomen") or "").strip(),
                "mobility": (request.POST.get("chart_mobility") or "").strip(),
                "eyesight_dexterity": (request.POST.get("chart_dexterity") or "").strip(),
                "education_given": bool(request.POST.get("chart_education")),
                "notes": (request.POST.get("chart_notes") or "").strip(),
            }
            if p.status == P.SITING_SCHEDULED:
                p.status = P.AWAITING_SURGERY
            p.save()
            E.objects.create(pathway=p, event_type=E.SITING, event_date=d,
                             summary="Stoma siting session completed",
                             education_given=bool(request.POST.get("chart_education")),
                             notes=(request.POST.get("chart_notes") or "").strip() or None,
                             data=p.siting_chart, recorded_by=who)
            messages.success(request, "Siting session recorded.")

        elif action == "record_surgery":
            d = _parse_date(request.POST.get("surgery_date"), today)
            p.surgery_date = d
            p.stoma_type = (request.POST.get("stoma_type") or "").strip() or p.stoma_type
            p.operation = (request.POST.get("operation") or "").strip() or p.operation
            p.status = P.INPATIENT
            p.save()
            E.objects.create(pathway=p, event_type=E.SURGERY, event_date=d,
                             summary="Surgery performed", recorded_by=who)
            messages.success(request, "Surgery recorded — start post-operative reviews.")

        elif action == "add_review":
            d = _parse_date(request.POST.get("event_date"), today)
            is_post_op = p.surgery_date is not None
            day = (d - p.surgery_date).days if is_post_op else None
            first = is_post_op and p.first_review_date is None
            if first:
                p.first_review_date = d
                p.save(update_fields=["first_review_date", "updated_at"])
            E.objects.create(
                pathway=p,
                event_type=E.POST_OP_REVIEW if is_post_op else E.REVIEW,
                event_date=d, day_number=day,
                summary=(request.POST.get("summary") or "").strip() or None,
                education_given=bool(request.POST.get("education_given")),
                supplies_given=bool(request.POST.get("supplies_given")),
                notes=(request.POST.get("notes") or "").strip() or None,
                recorded_by=who,
            )
            if first and p.first_review_was_late:
                messages.warning(
                    request,
                    f"First post-op review was day {p.first_review_delay_days} "
                    f"(not day 1) — flagged on this pathway.",
                )
            else:
                messages.success(request, "Review recorded.")

        elif action == "discharge":
            d = _parse_date(request.POST.get("discharge_date"), today)
            p.discharge_date = d
            # Fistulas are rarely followed up; everyone else becomes an
            # "old stoma" on follow-up once discharged.
            p.status = P.FOLLOWUP if p.expects_followup else P.CLOSED
            p.save()
            E.objects.create(pathway=p, event_type=E.DISCHARGE, event_date=d,
                             summary="Discharged", recorded_by=who)
            messages.success(
                request,
                "Discharged — now on follow-up." if p.expects_followup
                else "Discharged and closed.",
            )

        elif action == "add_appointment":
            d = _parse_date(request.POST.get("appt_date"))
            if not d:
                messages.error(request, "Enter a valid appointment date.")
            else:
                models.FollowUpAppointment.objects.create(
                    pathway=p, patient_id=p.patient_id, appt_date=d,
                    appt_time=(request.POST.get("appt_time") or "").strip() or None,
                    notes=(request.POST.get("appt_notes") or "").strip() or None,
                )
                messages.success(request, f"Appointment booked for {d:%d/%m/%Y}.")

        elif action == "close":
            p.status = P.CLOSED
            p.save(update_fields=["status", "updated_at"])
            messages.success(request, "Pathway closed.")

        elif action == "reopen":
            p.status = P.FOLLOWUP if p.discharge_date else P.INPATIENT
            p.save(update_fields=["status", "updated_at"])
            messages.success(request, "Pathway reopened.")

        else:
            messages.error(request, "Unknown action.")
    except Exception:
        messages.error(request, "That action could not be saved — please try again.")

    return redirect("clinic:pathway_detail", pk=p.pk)


@login_required
def appointments(request):
    """All planned follow-up / outpatient appointments."""
    show = (request.GET.get("show") or "upcoming").strip()

    def _load():
        qs = models.FollowUpAppointment.objects.select_related("patient", "pathway")
        if show == "upcoming":
            qs = qs.filter(appt_date__gte=datetime.date.today())
        return list(qs[:300])

    appts = _safe_query(_load, None)
    db_ok = appts is not None
    appts = appts or []

    if request.method == "POST":
        appt_id = (request.POST.get("appt_id") or "").strip()
        action = (request.POST.get("action") or "").strip()
        try:
            a = models.FollowUpAppointment.objects.get(pk=appt_id)
            if action == "reschedule":
                d = _parse_date(request.POST.get("appt_date"))
                if d:
                    a.appt_date = d
                    a.status = models.FollowUpAppointment.SCHEDULED
                    a.save()
                    messages.success(request, f"Moved to {d:%d/%m/%Y}.")
            elif action in dict(models.FollowUpAppointment.STATUS_CHOICES):
                a.status = action
                a.save(update_fields=["status", "updated_at"])
                messages.success(request, f"Marked as {a.get_status_display()}.")
        except Exception:
            messages.error(request, "Could not update that appointment.")
        return redirect("clinic:appointments")

    return render(request, "clinic/appointments.html", {
        "appointments": appts, "db_ok": db_ok, "show": show,
        "today": datetime.date.today(),
    })


@login_required
def add_patient(request):
    """Add a new patient and start their care pathway.

    Captures the pathway (elective / emergency / old case / fistula) alongside
    demographics, surgery details, clinical findings, history and consent,
    then opens the patient's pathway so the journey continues from here.
    """
    P = models.CarePathway
    ptype = ""
    if request.method == "POST":
        form = forms.PatientForm(request.POST)
        ptype = (request.POST.get("pathway_type") or "").strip()
        if ptype not in dict(P.TYPE_CHOICES):
            messages.error(request, "Choose a pathway for this patient.")
        elif form.is_valid():
            patient = form.save()
            setting = (request.POST.get("care_setting") or "").strip()
            siting = _parse_date(request.POST.get("siting_scheduled_date"))
            # Surgery may already be recorded on the patient record.
            surgery = patient.surgery_date

            # Where the pathway starts depends on its type.
            if ptype == P.ELECTIVE:
                status = P.SITING_SCHEDULED if siting else P.AWAITING_SURGERY
            elif ptype == P.EMERGENCY:
                status = P.INPATIENT if surgery else P.AWAITING_SURGERY
            elif ptype == P.OLD_CASE:
                status = (P.OUTPATIENT if setting == P.OUTPATIENT_SETTING
                          else P.INPATIENT)
            else:  # fistula — always seen as an inpatient
                status = P.INPATIENT

            pathway = P(
                patient=patient, pathway_type=ptype, status=status,
                siting_scheduled_date=siting if ptype == P.ELECTIVE else None,
                surgery_date=surgery,
                stoma_type=((request.POST.get("stoma_type") or "").strip()
                            or (patient.stoma_type_summary or "").strip() or None),
                operation=(patient.operation_performed or "").strip() or None,
                referral_source=(request.POST.get("referral_source") or "").strip() or None,
                care_setting=setting or None,
                created_by_username=request.user.get_username(),
            )
            try:
                pathway.save()
            except Exception:
                messages.success(request, "New patient added.")
                return redirect("clinic:patient_detail", patient_id=patient.id)

            if surgery:
                models.PathwayEvent.objects.create(
                    pathway=pathway, event_type=models.PathwayEvent.SURGERY,
                    event_date=surgery, summary="Surgery performed",
                    recorded_by=request.user.get_username(),
                )
            messages.success(request, "Patient added — pathway started.")
            return redirect("clinic:pathway_detail", pk=pathway.pk)
    else:
        form = forms.PatientForm()
    return render(request, "clinic/patient_form.html", {
        "form": form, "pathway_type": ptype,
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
    care_pathways = _safe_query(
        lambda: list(models.CarePathway.objects.filter(patient_id=patient_id)), []) or []
    return render(request, "clinic/patient_detail.html", {
        "patient": patient,
        "appointments": appointments,
        "episodes": episodes,
        "encounters": encounters,
        "followups": followups,
        "pathways": care_pathways,
    })
