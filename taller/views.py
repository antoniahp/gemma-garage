from datetime import date, timedelta

import re
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.management import call_command
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import services
from .forms import AppointmentForm, EditAppointmentForm
from .models import Appointment, Client, Invoice, LaborRate, Reminder
from .parser import parse_note

staff_required = user_passes_test(
    lambda u: u.is_active and u.is_staff, login_url="login"
)


def _back(request, fallback="home"):
    target = request.POST.get("next") or ""
    ok = url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    )
    return redirect(target if ok else fallback)


def _home_context(today, form=None):
    tomorrow = today + timedelta(days=1)
    todo = Appointment.objects.filter(status="pendiente").select_related("client")
    late = todo.filter(date__lt=today)
    return {
        "today": today, "tomorrow": tomorrow,
        "form": form or AppointmentForm(initial={"date": tomorrow}),
        "today_list": Appointment.objects.filter(date=today).select_related("client"),
        "tomorrow_list": Appointment.objects.filter(date=tomorrow).select_related("client"),
        "late_list": late,
        "to_order": [a for a in todo.filter(ordered=False, date__gte=today)
                     if a.order_state == "pedir_hoy"],
        "failed": todo.filter(ordered=False).exclude(order_error="").count(),
        "reminders": Reminder.objects.filter(sent=False).select_related("client")[:5],
        "clients": Client.objects.values_list("name", flat=True),
        "tab": "home",
    }


@staff_required
def home(request):
    return render(request, "taller/home.html", _home_context(timezone.localdate()))


@staff_required
def week(request):
    today = timezone.localdate()
    try:
        ref = date.fromisoformat(request.GET.get("d", ""))
    except ValueError:
        ref = today
    start = ref - timedelta(days=ref.weekday())
    days = []
    for i in range(7):
        d = start + timedelta(days=i)
        days.append({
            "date": d, "is_today": d == today, "weekend": d.weekday() >= 5,
            "items": Appointment.objects.filter(date=d).select_related("client"),
        })
    return render(request, "taller/week.html", {
        "days": days, "start": start, "end": start + timedelta(days=6), "today": today,
        "prev": start - timedelta(days=7), "next": start + timedelta(days=7),
        "tab": "week",
    })


@staff_required
def clients(request):
    q = request.GET.get("q", "").strip()
    qs = Client.objects.annotate(
        visits=Count("appointments"),
        waiting=Count("reminder", filter=Q(reminder__sent=False)),
    )
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(phone__icontains=q))
    return render(request, "taller/clients.html", {"clients": qs, "q": q, "tab": "clients"})


@staff_required
def invoices(request):
    qs = Invoice.objects.select_related("appointment__client")
    return render(request, "taller/invoices.html", {"invoices": qs, "tab": "invoices"})


@staff_required
@require_POST
def appointment_create(request):
    today = timezone.localdate()
    form = AppointmentForm(request.POST)
    if not form.is_valid():
        ctx = _home_context(today, form)
        return render(request, "taller/home.html", ctx, status=400)
    data = form.cleaned_data
    client = Client.objects.filter(name__iexact=data["client_name"]).first()
    if client is None:
        client = Client.objects.create(name=data["client_name"], phone=data["phone"])
    elif data["phone"] and not client.phone:
        client.phone = data["phone"]
        client.save(update_fields=["phone"])
    appt = Appointment.objects.create(
        client=client, date=data["date"], plate=data["plate"], note=data["note"],
        vehicle=data["vehicle"],
    )
    extra = f" Aviso programado cada {appt.repeat_months} meses." if appt.repeat_months else ""
    messages.success(request, f"Cita apuntada: {appt.service or appt.note}.{extra}")
    if data["date"] in (today, today + timedelta(days=1)):
        return redirect("home")
    return redirect(f"{reverse('week')}?d={data['date'].isoformat()}")


@staff_required
@require_POST
def appointment_order(request, pk):
    appt = get_object_or_404(Appointment, pk=pk)
    if appt.ordered or not appt.parts:
        messages.info(request, "Esta cita no tiene recambios pendientes de pedir.")
    else:
        try:
            services.order_parts(appt)
            messages.success(request, f"Recambios pedidos para {appt.client.name}.")
        except Exception as exc:
            messages.error(request, f"No se pudo hacer el pedido: {exc}")
    return _back(request)


@staff_required
@require_POST
def appointment_done(request, pk):
    appt = get_object_or_404(Appointment, pk=pk)
    inv = services.complete_and_invoice(appt)
    messages.success(request, format_html(
        'Cita hecha. Factura {} lista: <a href="{}" target="_blank">abrir e imprimir</a>.',
        inv.number, reverse("invoice", args=[appt.pk]),
    ))
    return _back(request)


@staff_required
@require_POST
def run_daily_view(request):
    report = services.run_daily()
    msg = f"Pedidos enviados: {len(report['orders'])}. Avisos enviados: {len(report['reminders'])}."
    messages.success(request, msg)
    for err in report["errors"]:
        messages.error(request, err)
    return _back(request)


@staff_required
def interpret(request):
    parsed = parse_note(request.GET.get("note", ""), vehicle=request.GET.get("vehicle", ""))  # con Gemma si Ollama está activo
    return JsonResponse({
        "service": parsed["service"], "vehicle": parsed["vehicle"],
        "repeat_months": parsed["repeat_months"], "parts": parsed["parts"],
        "engine": parsed["engine"], "llm_error": parsed.get("llm_error", ""),
    })


@staff_required
def invoice(request, appointment_id):
    inv = get_object_or_404(
        Invoice.objects.select_related("appointment__client"), appointment_id=appointment_id
    )
    return render(request, "taller/invoice.html", {"inv": inv, "appt": inv.appointment})


# ---------------------------------------------------------------- pedido revisable

def _norm_plate(text):
    return re.sub(r"[^A-Z0-9]", "", (text or "").upper())


@staff_required
def order_review(request):
    """Recambios por pedir, editables antes de enviarlos al proveedor."""
    today = timezone.localdate()
    if request.method == "POST":
        pending = {a.pk: a for a in Appointment.objects.filter(
            pk__in=[int(i) for i in request.POST.getlist("ids") if i.isdigit()],
            status="pendiente", ordered=False)}
        for pk, appt in pending.items():
            parts = services.parts_from_post(request.POST, pk)
            if parts != appt.parts:
                appt.parts = parts
                Appointment.objects.filter(pk=pk).update(parts=parts)
        if request.POST.get("do") == "send":
            sent = 0
            for raw in request.POST.getlist("send"):
                appt = pending.get(int(raw)) if raw.isdigit() else None
                if appt is None or not appt.parts:
                    continue
                try:
                    services.order_parts(appt)
                    sent += 1
                except Exception as exc:
                    messages.error(request, f"{appt.client.name}: no se pudo pedir ({exc}).")
            if sent:
                messages.success(request, f"Pedidos enviados: {sent}.")
            else:
                messages.info(request, "No había nada seleccionado para enviar.")
        else:
            messages.success(request, "Cambios guardados.")
        return redirect("order_review")
    appts = Appointment.objects.filter(
        status="pendiente", ordered=False, date__gte=today, date__lte=today + timedelta(days=7)
    ).select_related("client")
    rows = [{"a": a, "checked": bool(a.parts) and a.order_state in ("pedir_hoy", "fallo")}
            for a in appts]
    rows.sort(key=lambda r: (not r["checked"], r["a"].date))
    return render(request, "taller/order_review.html", {
        "rows": rows, "today": today,
        "shopping_day": services.next_business_day(today), "tab": "order",
    })


@staff_required
def shopping(request):
    """Lista de compra: todos los recambios de un día, sumados."""
    today = timezone.localdate()
    try:
        day = date.fromisoformat(request.GET.get("d", ""))
    except ValueError:
        day = services.next_business_day(today)
    appts = list(Appointment.objects.filter(date=day, status="pendiente").select_related("client"))
    return render(request, "taller/shopping.html", {
        "day": day, "rows": services.shopping_list(appts), "appts": appts,
        "prev": services.previous_business_day(day), "next": services.next_business_day(day),
        "tab": "order",
    })


# ---------------------------------------------------------------- editar cita

@staff_required
def appointment_edit(request, pk):
    appt = get_object_or_404(Appointment.objects.select_related("client"), pk=pk)
    if request.method == "POST":
        form = EditAppointmentForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            client = Client.objects.filter(name__iexact=d["client_name"]).first() \
                or Client.objects.create(name=d["client_name"])
            if d["phone"] and client.phone != d["phone"]:
                client.phone = d["phone"]
                client.save(update_fields=["phone"])
            old = (appt.date, appt.repeat_months)
            old_parts = appt.parts
            appt.client, appt.date, appt.plate, appt.note = client, d["date"], d["plate"], d["note"]
            appt.vehicle = d["vehicle"]
            if d["reinterpret"]:
                appt.interpret_note()
            else:
                appt.service = d["service"]
                appt.repeat_months = d["repeat_months"] or 0
                appt.parts = services.parts_from_post(request.POST, appt.pk)
            appt.save()
            if (appt.date, appt.repeat_months) != old:
                Reminder.objects.filter(appointment=appt, sent=False).delete()
                if appt.repeat_months:
                    services.schedule_reminder(appt)
            if appt.ordered and appt.parts != old_parts:
                messages.info(request, "Los recambios ya estaban pedidos: el cambio no se ha reenviado al proveedor.")
            messages.success(request, "Cita guardada.")
            return redirect(f"{reverse('week')}?d={appt.date.isoformat()}")
    else:
        form = EditAppointmentForm(initial={
            "date": appt.date, "client_name": appt.client.name, "phone": appt.client.phone,
            "plate": appt.plate, "note": appt.note, "service": appt.service,
            "vehicle": appt.vehicle, "repeat_months": appt.repeat_months,
        })
    return render(request, "taller/edit.html", {"form": form, "a": appt, "tab": "week"})


# ---------------------------------------------------------------- historial, búsqueda

@staff_required
def history(request):
    plate = _norm_plate(request.GET.get("plate", ""))
    if len(plate) < 4:
        return JsonResponse({"found": False})
    rows = [a for a in Appointment.objects.exclude(plate="").select_related("client").order_by("-date")
            if _norm_plate(a.plate) == plate][:5]
    if not rows:
        return JsonResponse({"found": False})
    last = rows[0]
    return JsonResponse({
        "found": True, "client": last.client.name, "phone": last.client.phone,
        "vehicle": last.vehicle,
        "visits": [{
            "date": a.date.strftime("%d/%m/%Y"), "service": a.service or a.note,
            "parts": ", ".join(f"{p['qty']} {p['name']} {p.get('spec', '')}".strip() for p in a.parts),
        } for a in rows],
    })


@staff_required
def search(request):
    q = request.GET.get("q", "").strip()
    found = []
    if q:
        norm = _norm_plate(q)
        cond = (Q(note__icontains=q) | Q(plate__icontains=q) | Q(client__name__icontains=q)
                | Q(vehicle__icontains=q) | Q(service__icontains=q) | Q(client__phone__icontains=q))
        found = list(Appointment.objects.filter(cond).select_related("client").order_by("-date")[:60])
        if norm and len(norm) >= 4:  # "1234 abc" también encuentra "1234ABC"
            extra = [a for a in Appointment.objects.exclude(plate="").select_related("client")
                     if norm in _norm_plate(a.plate) and a not in found]
            found = sorted(found + extra, key=lambda a: a.date, reverse=True)[:60]
    return render(request, "taller/search.html", {"q": q, "found": found, "tab": ""})


# ---------------------------------------------------------------- copia y tarifas

@staff_required
def backup(request):
    from io import StringIO

    out = StringIO()
    call_command("dumpdata", "taller", indent=2, stdout=out)
    resp = HttpResponse(out.getvalue(), content_type="application/json; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="copia-taller-{timezone.localdate()}.json"'
    return resp


def _parse_price(text):
    try:
        value = Decimal(str(text).replace(",", ".").strip())
    except InvalidOperation:
        return None
    return value.quantize(Decimal("0.01")) if 0 <= value < 100000 else None


@staff_required
def prices(request):
    """Mano de obra por trabajo. Los recambios no tienen precio: dependen del distribuidor."""
    if request.method == "POST":
        pairs = list(zip(request.POST.getlist("p_name"), request.POST.getlist("p_price")))
        new_name, new_price = request.POST.get("new_name", "").strip(), request.POST.get("new_price", "").strip()
        if new_name or new_price:
            pairs.append((new_name, new_price))
        todo, bad = [], []
        for name, raw in pairs:
            name = " ".join(name.split())
            if not raw.strip() and name:
                todo.append((name, None))  # precio vacío = sin tarifa
                continue
            value = _parse_price(raw)
            if not name or value is None:
                bad.append(name or "(sin nombre)")
            else:
                todo.append((name, value))
        if bad:
            messages.error(request, "Revisa el precio de: " + ", ".join(bad) + ". Usa números, por ejemplo 45 o 37,50.")
        else:
            for name, value in todo:
                if value is None:
                    LaborRate.objects.filter(service=name).delete()
                else:
                    LaborRate.objects.update_or_create(service=name, defaults={"price": value})
            messages.success(request, "Tarifas guardadas.")
            return redirect("prices")
    saved = {r.service: r.price for r in LaborRate.objects.all()}
    names = list(services.KNOWN_SERVICES) + sorted(set(saved) - set(services.KNOWN_SERVICES), key=str.lower)
    rows = [{"name": n, "price": f"{saved[n]:.2f}".replace(".", ",") if n in saved else ""} for n in names]
    return render(request, "taller/prices.html", {"rows": rows, "iva": int(services.IVA * 100), "tab": "prices"})


@staff_required
def appointment_invoice(request, pk):
    """Pantalla para facturar: precio de cada recambio (según el albarán) y mano de obra."""
    appt = get_object_or_404(Appointment.objects.select_related("client"), pk=pk)
    if hasattr(appt, "invoice"):
        return redirect("invoice", appt.pk)
    post = request.POST if request.method == "POST" else None
    labor_default = services.labor_price(appt.service)
    rows = [{"i": i, "p": p, "price": post.get(f"price_{i}", "") if post else ""}
            for i, p in enumerate(appt.parts)]
    ctx = {
        "a": appt, "rows": rows, "iva": services.IVA, "iva_pct": int(services.IVA * 100), "tab": "invoices",
        "labor": post.get("labor", "") if post else (f"{labor_default:.2f}".replace(".", ",") if labor_default is not None else ""),
        "extra_concept": post.get("extra_concept", "") if post else "",
        "extra_price": post.get("extra_price", "") if post else "",
    }
    if post is None:
        return render(request, "taller/invoice_form.html", ctx)

    prices_, bad = [], []
    for r in rows:
        raw = r["price"].strip()
        value = Decimal("0") if not raw else _parse_price(raw)
        if value is None:
            bad.append(r["p"]["name"])
        prices_.append(value)
    labor = Decimal("0") if not ctx["labor"].strip() else _parse_price(ctx["labor"])
    if labor is None:
        bad.append("mano de obra")
    extras = []
    if ctx["extra_concept"].strip() or ctx["extra_price"].strip():
        extra = _parse_price(ctx["extra_price"])
        if extra is None or not ctx["extra_concept"].strip():
            bad.append("línea adicional")
        else:
            extras.append((ctx["extra_concept"].strip(), extra))
    if bad:
        messages.error(request, "Revisa los importes de: " + ", ".join(bad) + ". Usa números, por ejemplo 12,50.")
        return render(request, "taller/invoice_form.html", ctx, status=400)
    inv = services.complete_and_invoice(appt, part_prices=prices_, labor=labor, extras=extras)
    messages.success(request, format_html(
        'Cita hecha. Factura {} lista: <a href="{}" target="_blank">abrir e imprimir</a>.',
        inv.number, reverse("invoice", args=[appt.pk]),
    ))
    return redirect("home")
