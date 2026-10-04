"""Adaptador web: traduce peticiones HTTP a comandos/consultas de la capa de aplicación."""

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from io import StringIO

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.management import call_command
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from taller import container
from taller.application.build_shopping_list.build_shopping_list_query import BuildShoppingListQuery
from taller.application.complete_and_invoice_appointment.complete_and_invoice_appointment_command import (
    CompleteAndInvoiceAppointmentCommand,
)
from taller.application.create_appointment.create_appointment_command import CreateAppointmentCommand
from taller.application.edit_appointment.edit_appointment_command import EditAppointmentCommand
from taller.application.find_appointment.find_appointment_query import FindAppointmentQuery
from taller.application.find_clients.find_clients_query import FindClientsQuery
from taller.application.find_home_board.find_home_board_query import FindHomeBoardQuery
from taller.application.find_invoice.find_invoice_query import FindInvoiceQuery
from taller.application.find_invoices.find_invoices_query import FindInvoicesQuery
from taller.application.find_labor_price.find_labor_price_query import FindLaborPriceQuery
from taller.application.find_labor_rates.find_labor_rates_query import FindLaborRatesQuery
from taller.application.find_order_review.find_order_review_query import FindOrderReviewQuery
from taller.application.find_plate_history.find_plate_history_query import FindPlateHistoryQuery
from taller.application.find_week.find_week_query import FindWeekQuery
from taller.application.interpret_note.interpret_note_query import InterpretNoteQuery
from taller.application.order_appointment_parts.order_appointment_parts_command import (
    OrderAppointmentPartsCommand,
)
from taller.application.review_parts_order.review_parts_order_command import ReviewPartsOrderCommand
from taller.application.run_daily.run_daily_command import RunDailyCommand
from taller.application.save_labor_rates.save_labor_rates_command import SaveLaborRatesCommand
from taller.application.search_appointments.search_appointments_query import SearchAppointmentsQuery
from taller.domain.business_calendar import next_business_day, previous_business_day
from taller.domain.exceptions.appointment_not_found_exception import AppointmentNotFoundException
from taller.domain.exceptions.invoice_not_found_exception import InvoiceNotFoundException
from taller.domain.known_services import KNOWN_SERVICES  # noqa: F401  (se usa desde las plantillas/tests)
from taller.domain.money import IVA

from .forms import AppointmentForm, EditAppointmentForm, parts_from_post

staff_required = user_passes_test(
    lambda u: u.is_active and u.is_staff, login_url="login"
)


def _back(request, fallback="home"):
    target = request.POST.get("next") or ""
    ok = url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    )
    return redirect(target if ok else fallback)


def _find_appointment_or_404(pk):
    try:
        return container.find_appointment_handler().handle(FindAppointmentQuery(appointment_id=pk))
    except AppointmentNotFoundException:
        raise Http404


def _home_context(today, form=None):
    board = container.find_home_board_handler().handle(FindHomeBoardQuery(today=today))
    tomorrow = today + timedelta(days=1)
    return {
        "today": today, "tomorrow": tomorrow,
        "form": form or AppointmentForm(initial={"date": tomorrow}),
        **board, "tab": "home",
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
    data = container.find_week_handler().handle(FindWeekQuery(reference=ref, today=today))
    return render(request, "taller/week.html", {**data, "today": today, "tab": "week"})


@staff_required
def clients(request):
    q = request.GET.get("q", "").strip()
    found = container.find_clients_handler().handle(FindClientsQuery(text=q))
    return render(request, "taller/clients.html", {"clients": found, "q": q, "tab": "clients"})


@staff_required
def invoices(request):
    found = container.find_invoices_handler().handle(FindInvoicesQuery())
    return render(request, "taller/invoices.html", {"invoices": found, "tab": "invoices"})


@staff_required
@require_POST
def appointment_create(request):
    today = timezone.localdate()
    form = AppointmentForm(request.POST)
    if not form.is_valid():
        ctx = _home_context(today, form)
        return render(request, "taller/home.html", ctx, status=400)
    data = form.cleaned_data
    appt = container.create_appointment_handler().handle(CreateAppointmentCommand(
        date=data["date"], client_name=data["client_name"], note=data["note"],
        phone=data["phone"], plate=data["plate"], vehicle=data["vehicle"],
    ))
    extra = f" Aviso programado cada {appt.repeat_months} meses." if appt.repeat_months else ""
    messages.success(request, f"Cita apuntada: {appt.service or appt.note}.{extra}")
    if data["date"] in (today, today + timedelta(days=1)):
        return redirect("home")
    return redirect(f"{reverse('week')}?d={data['date'].isoformat()}")


@staff_required
@require_POST
def appointment_order(request, pk):
    appt = _find_appointment_or_404(pk)
    if appt.ordered or not appt.parts:
        messages.info(request, "Esta cita no tiene recambios pendientes de pedir.")
    else:
        try:
            container.order_appointment_parts_handler().handle(OrderAppointmentPartsCommand(appointment_id=pk))
            messages.success(request, f"Recambios pedidos para {appt.client.name}.")
        except Exception as exc:
            messages.error(request, f"No se pudo hacer el pedido: {exc}")
    return _back(request)


@staff_required
@require_POST
def appointment_done(request, pk):
    _find_appointment_or_404(pk)
    inv = container.complete_and_invoice_handler().handle(CompleteAndInvoiceAppointmentCommand(appointment_id=pk))
    messages.success(request, format_html(
        'Cita hecha. Factura {} lista: <a href="{}" target="_blank">abrir e imprimir</a>.',
        inv.number, reverse("invoice", args=[pk]),
    ))
    return _back(request)


@staff_required
@require_POST
def run_daily_view(request):
    report = container.run_daily_handler().handle(RunDailyCommand())
    msg = f"Pedidos enviados: {len(report['orders'])}. Avisos enviados: {len(report['reminders'])}."
    messages.success(request, msg)
    for err in report["errors"]:
        messages.error(request, err)
    return _back(request)


@staff_required
def interpret(request):
    parsed = container.interpret_note_handler().handle(InterpretNoteQuery(
        note=request.GET.get("note", ""), vehicle=request.GET.get("vehicle", "")))  # con Gemma si Ollama está activo
    return JsonResponse({
        "service": parsed.service, "vehicle": parsed.vehicle,
        "repeat_months": parsed.repeat_months, "parts": parsed.parts,
        "engine": parsed.engine, "llm_error": parsed.llm_error,
    })


@staff_required
def invoice(request, appointment_id):
    try:
        inv = container.find_invoice_handler().handle(FindInvoiceQuery(appointment_id=appointment_id))
    except InvoiceNotFoundException:
        raise Http404
    return render(request, "taller/invoice.html", {"inv": inv, "appt": inv.appointment})


# ---------------------------------------------------------------- pedido revisable

@staff_required
def order_review(request):
    """Recambios por pedir, editables antes de enviarlos al proveedor."""
    today = timezone.localdate()
    if request.method == "POST":
        ids = tuple(int(i) for i in request.POST.getlist("ids") if i.isdigit())
        do_send = request.POST.get("do") == "send"
        result = container.review_parts_order_handler().handle(ReviewPartsOrderCommand(
            appointment_ids=ids,
            parts_by_appointment={pk: parts_from_post(request.POST, pk) for pk in ids},
            send_ids=tuple(int(r) for r in request.POST.getlist("send") if r.isdigit()),
            send=do_send,
        ))
        if do_send:
            for err in result["errors"]:
                messages.error(request, err)
            if result["sent"]:
                messages.success(request, f"Pedidos enviados: {result['sent']}.")
            else:
                messages.info(request, "No había nada seleccionado para enviar.")
        else:
            messages.success(request, "Cambios guardados.")
        return redirect("order_review")
    rows = container.find_order_review_handler().handle(FindOrderReviewQuery(today=today))
    return render(request, "taller/order_review.html", {
        "rows": rows, "today": today, "shopping_day": next_business_day(today), "tab": "order",
    })


@staff_required
def shopping(request):
    """Lista de compra: todos los recambios de un día, sumados."""
    today = timezone.localdate()
    try:
        day = date.fromisoformat(request.GET.get("d", ""))
    except ValueError:
        day = next_business_day(today)
    data = container.build_shopping_list_handler().handle(BuildShoppingListQuery(day=day))
    return render(request, "taller/shopping.html", {
        "day": day, "rows": data["rows"], "appts": data["appointments"],
        "prev": previous_business_day(day), "next": next_business_day(day), "tab": "order",
    })


# ---------------------------------------------------------------- editar cita

@staff_required
def appointment_edit(request, pk):
    appt = _find_appointment_or_404(pk)
    if request.method == "POST":
        form = EditAppointmentForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            old_parts = appt.parts
            appt = container.edit_appointment_handler().handle(EditAppointmentCommand(
                appointment_id=pk, date=d["date"], client_name=d["client_name"], note=d["note"],
                phone=d["phone"], plate=d["plate"], vehicle=d["vehicle"], service=d["service"],
                repeat_months=d["repeat_months"] or 0, parts=tuple(parts_from_post(request.POST, pk)),
                reinterpret=d["reinterpret"],
            ))
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
    return JsonResponse(container.find_plate_history_handler().handle(
        FindPlateHistoryQuery(plate=request.GET.get("plate", ""))))


@staff_required
def search(request):
    q = request.GET.get("q", "").strip()
    found = container.search_appointments_handler().handle(SearchAppointmentsQuery(text=q))
    return render(request, "taller/search.html", {"q": q, "found": found, "tab": ""})


# ---------------------------------------------------------------- copia y tarifas

@staff_required
def backup(request):
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


def _price_text(value):
    return f"{value:.2f}".replace(".", ",") if value is not None else ""


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
            container.save_labor_rates_handler().handle(SaveLaborRatesCommand(entries=tuple(todo)))
            messages.success(request, "Tarifas guardadas.")
            return redirect("prices")
    rows = [{"name": r["name"], "price": _price_text(r["price"])}
            for r in container.find_labor_rates_handler().handle(FindLaborRatesQuery())]
    return render(request, "taller/prices.html", {"rows": rows, "iva": int(IVA * 100), "tab": "prices"})


@staff_required
def appointment_invoice(request, pk):
    """Pantalla para facturar: precio de cada recambio (según el albarán) y mano de obra."""
    appt = _find_appointment_or_404(pk)
    if container.find_invoice_handler().find_or_none(FindInvoiceQuery(appointment_id=pk)):
        return redirect("invoice", pk)
    post = request.POST if request.method == "POST" else None
    labor_default = container.find_labor_price_handler().handle(FindLaborPriceQuery(service=appt.service))
    rows = [{"i": i, "p": p, "price": post.get(f"price_{i}", "") if post else ""}
            for i, p in enumerate(appt.parts)]
    ctx = {
        "a": appt, "rows": rows, "iva": IVA, "iva_pct": int(IVA * 100), "tab": "invoices",
        "labor": post.get("labor", "") if post else _price_text(labor_default),
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
    inv = container.complete_and_invoice_handler().handle(CompleteAndInvoiceAppointmentCommand(
        appointment_id=pk, part_prices=tuple(prices_), labor=labor, extras=tuple(extras)))
    messages.success(request, format_html(
        'Cita hecha. Factura {} lista: <a href="{}" target="_blank">abrir e imprimir</a>.',
        inv.number, reverse("invoice", args=[pk]),
    ))
    return redirect("home")
