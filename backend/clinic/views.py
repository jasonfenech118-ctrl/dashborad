import calendar
import datetime
import json
import time
import urllib.parse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMultiAlternatives
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404
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
        try:
            stoma = patient.stomas.filter(status=models.Stoma.ACTIVE).first()
        except Exception:
            stoma = None
        prefill = {
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
    try:
        stomas = list(patient.stomas.all())
    except Exception:
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
    try:
        return fn()
    except Exception:
        return default


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


# ---------------------------------------------------------------- library


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
    docs, db_ok = [], True
    try:
        qs = models.LibraryDocument.objects.all()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
        if cat:
            qs = qs.filter(category=cat)
        docs = list(qs[:300])
    except Exception:
        db_ok = False

    return render(request, "clinic/library.html", {
        "documents": docs, "db_ok": db_ok, "q": q, "category": cat,
        "categories": models.LibraryDocument.CATEGORY_CHOICES,
    })


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
    open_count = closed_count = None
    db_ok = True
    try:
        T = models.TenderEvaluation
        open_count = T.objects.filter(status=T.STATUS_OPEN).count()
        closed_count = T.objects.filter(status=T.STATUS_CLOSED).count()
    except Exception:
        db_ok = False
    return render(request, "clinic/cpsu_tenders.html", {
        "open_count": open_count, "closed_count": closed_count, "db_ok": db_ok,
    })


def _tender_list(request, status, title):
    tenders, db_ok = [], True
    try:
        tenders = list(models.TenderEvaluation.objects.filter(status=status)[:300])
    except Exception:
        db_ok = False
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
        messages.success(request, f"Tender “{tender.title}” closed and saved.")
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
    appts, db_ok = [], True
    show = (request.GET.get("show") or "upcoming").strip()
    try:
        qs = models.FollowUpAppointment.objects.select_related("patient", "pathway")
        if show == "upcoming":
            qs = qs.filter(appt_date__gte=datetime.date.today())
        appts = list(qs[:300])
    except Exception:
        db_ok = False

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
    try:
        care_pathways = list(
            models.CarePathway.objects.filter(patient_id=patient_id)
        )
    except Exception:
        care_pathways = []
    return render(request, "clinic/patient_detail.html", {
        "patient": patient,
        "appointments": appointments,
        "episodes": episodes,
        "encounters": encounters,
        "followups": followups,
        "pathways": care_pathways,
    })
