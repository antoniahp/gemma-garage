"""Lógica del taller: pedidos automáticos, avisos anuales y facturas."""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
import calendar

from django.db import transaction
from django.utils import timezone

from .channels import get_notifier, get_supplier
from .models import Appointment, Invoice, LaborRate, Order, Reminder

IVA = Decimal("0.21")
# Trabajos que reconoce el programa; el taller pone el precio de la mano de obra de cada uno
# en la pantalla Tarifas. Los recambios NO tienen precio guardado (dependen del distribuidor):
# se escriben al facturar.
KNOWN_SERVICES = [
    "cambio de aceite", "ITV", "cambio de neumáticos", "cambio de pastillas de freno",
    "revisión de frenos", "cambio de filtros", "cambio de correa de distribución",
    "cambio de batería",
]


def add_months(d, months):
    """Suma meses respetando fin de mes (29 feb -> 28 feb)."""
    index = d.month - 1 + months
    year, month = d.year + index // 12, index % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def previous_business_day(d):
    """Día laborable anterior (el lunes se pide el viernes)."""
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def next_business_day(d):
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def money(x):
    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def schedule_reminder(appointment):
    """Programa el aviso para una semana antes de que se cumpla el plazo."""
    next_date = add_months(appointment.date, appointment.repeat_months)
    plate = f" ({appointment.plate})" if appointment.plate else ""
    message = (
        f"Hola {appointment.client.name}, desde el taller le recordamos que a su vehículo"
        f"{plate} le toca {appointment.service} sobre el {next_date.strftime('%d/%m/%Y')}. "
        f"Llámenos y le damos cita."
    )
    return Reminder.objects.create(
        client=appointment.client,
        appointment=appointment,
        send_on=next_date - timedelta(days=7),
        message=message,
    )


def order_parts(appointment, supplier=None):
    """Envía el pedido de una cita. Lanza excepción si el proveedor falla."""
    supplier = supplier or get_supplier()
    order = {
        "appointment_id": appointment.pk,
        "deliver_on": appointment.date.isoformat(),
        "service": appointment.service,
        "vehicle": appointment.vehicle,
        "plate": appointment.plate,
        "parts": appointment.parts,
    }
    try:
        detail = supplier.send_order(order)
    except Exception as exc:
        Appointment.objects.filter(pk=appointment.pk).update(order_error=str(exc)[:200] or "error")
        raise
    with transaction.atomic():
        Order.objects.create(
            appointment=appointment, supplier=supplier.name,
            parts=appointment.parts, detail=detail,
        )
        Appointment.objects.filter(pk=appointment.pk).update(ordered=True, order_error="")
    return detail


def parse_qty(text):
    """'4', '1,5' -> número; devuelve None si no es válido o no es positivo."""
    try:
        qty = float(str(text).replace(",", ".").strip())
    except ValueError:
        return None
    if qty <= 0:
        return None
    return int(qty) if qty == int(qty) else qty


def parts_from_post(post, pk):
    """Lee las líneas de recambios de un formulario (campos name_<pk>, spec_<pk>, ...).

    Las líneas sin nombre se descartan; así se borra una línea vaciándola.
    """
    names, specs = post.getlist(f"name_{pk}"), post.getlist(f"spec_{pk}")
    qtys, units = post.getlist(f"qty_{pk}"), post.getlist(f"unit_{pk}")
    parts = []
    for i, name in enumerate(names):
        name = " ".join(name.split())
        if not name:
            continue
        qty = parse_qty(qtys[i]) if i < len(qtys) else 1
        parts.append({
            "name": name,
            "spec": " ".join(specs[i].split()) if i < len(specs) else "",
            "qty": qty or 1,
            "unit": (units[i].strip() if i < len(units) else "") or "ud",
        })
    return parts


def shopping_list(appointments):
    """Suma los recambios iguales de varias citas: [(nombre, spec, unidad, total, [coches])]."""
    totals = {}
    for appt in appointments:
        car = " ".join(x for x in (appt.vehicle, appt.plate) if x) or appt.client.name
        for p in appt.parts:
            key = (p["name"].lower(), p.get("spec", "").upper(), p.get("unit", "ud"))
            row = totals.setdefault(key, {"name": p["name"], "spec": p.get("spec", ""),
                                          "unit": p.get("unit", "ud"), "qty": 0, "cars": []})
            row["qty"] += p["qty"]
            if car not in row["cars"]:
                row["cars"].append(car)
    rows = sorted(totals.values(), key=lambda r: r["name"].lower())
    for r in rows:
        r["qty"] = round(r["qty"], 2)
        if r["qty"] == int(r["qty"]):
            r["qty"] = int(r["qty"])
    return rows


def run_daily(today=None):
    """Tarea diaria: pide los recambios que toquen y envía los avisos pendientes.

    Se pide el día laborable anterior a la cita. Si un día no se ejecutó, la
    siguiente ejecución pide igualmente lo que falte. Nunca duplica pedidos.
    """
    today = today or timezone.localdate()
    notifier = get_notifier()
    report = {"orders": [], "reminders": [], "errors": []}

    pending = Appointment.objects.filter(
        ordered=False, status="pendiente", date__gte=today
    ).select_related("client")
    for appt in pending:
        if previous_business_day(appt.date) > today or not appt.parts:
            continue
        try:
            detail = order_parts(appt)
        except Exception as exc:  # si falla, no se marca como pedido y se reintenta
            report["errors"].append(f"pedido cita {appt.pk}: {exc}")
            continue
        report["orders"].append({"appointment_id": appt.pk, "detail": detail})

    due = Reminder.objects.filter(sent=False, send_on__lte=today).select_related("client")
    for reminder in due:
        ok, detail = notifier.notify_client(reminder.client, reminder.message)
        if ok:
            Reminder.objects.filter(pk=reminder.pk).update(sent=True, detail=detail[:200])
            report["reminders"].append({"reminder_id": reminder.pk, "detail": detail})
        else:
            report["errors"].append(f"aviso {reminder.pk}: {detail}")

    if report["orders"] or report["reminders"]:
        lines = [f"Resumen del {today.strftime('%d/%m/%Y')}:"]
        lines += [f"- Recambios pedidos para la cita {o['appointment_id']}" for o in report["orders"]]
        lines += [f"- Avisos enviados: {len(report['reminders'])}"] if report["reminders"] else []
        notifier.notify_owner("\n".join(lines))
    return report


def _norm(text):
    import unicodedata

    text = unicodedata.normalize("NFD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).lower().strip()


def labor_price(service):
    """Precio de mano de obra de un trabajo, o None si no hay tarifa.

    Primero busca el nombre exacto y luego el más largo que esté contenido en el trabajo
    ("cambio de aceite y filtro" -> "cambio de aceite").
    """
    rates = {_norm(r.service): r.price for r in LaborRate.objects.all()}
    key = _norm(service)
    if key in rates:
        return rates[key]
    for name in sorted(rates, key=len, reverse=True):
        if name and (name in key or key in name):
            return rates[name]
    return None


@transaction.atomic
def complete_and_invoice(appointment, part_prices=None, labor=None, extras=()):
    """Marca la cita como hecha y genera la factura (una por cita).

    part_prices: precio unitario de cada recambio, en el mismo orden que appointment.parts
                 (los recambios no tienen precio guardado: dependen del distribuidor).
    labor:       importe de la mano de obra; si no se da, se usa la tarifa del trabajo.
    extras:      lista de (concepto, importe) adicionales.
    """
    existing = Invoice.objects.filter(appointment=appointment).first()
    if existing:
        return existing

    part_prices = list(part_prices or [])
    lines = []
    for i, p in enumerate(appointment.parts):
        qty = Decimal(str(p["qty"]))
        price = Decimal(part_prices[i]) if i < len(part_prices) and part_prices[i] is not None else Decimal("0")
        lines.append({
            "concept": f"{p['name']} {p.get('spec', '')}".strip(),
            "qty": str(qty), "unit_price": str(money(price)), "amount": str(money(qty * price)),
        })
    if labor is None:
        labor = labor_price(appointment.service)
    if labor:
        lines.append({
            "concept": f"Mano de obra: {appointment.service}",
            "qty": "1", "unit_price": str(money(labor)), "amount": str(money(labor)),
        })
    for concept, amount in extras:
        lines.append({"concept": concept, "qty": "1", "unit_price": str(money(amount)),
                      "amount": str(money(amount))})
    subtotal = money(sum(Decimal(l["amount"]) for l in lines))
    iva = money(subtotal * IVA)
    today = timezone.localdate()
    count = Invoice.objects.filter(created_at__year=today.year).count() + 1
    invoice = Invoice.objects.create(
        appointment=appointment, number=f"{today.year}-{count:04d}", created_at=today,
        lines=lines, subtotal=subtotal, iva=iva, total=subtotal + iva,
    )
    Appointment.objects.filter(pk=appointment.pk).update(status="hecha")
    return invoice
