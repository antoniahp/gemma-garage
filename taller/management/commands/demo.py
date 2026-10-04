"""Datos de ejemplo (ficticios) para probar y para hacer capturas de la agenda.

    python manage.py demo            # solo si la agenda está vacía
    python manage.py demo --reset    # borra clientes, citas, pedidos, avisos y facturas y carga el ejemplo

Antes de borrar guarda una copia en un archivo .json. No toca usuarios ni tarifas.
"""

from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from taller import container
from taller.application.complete_and_invoice_appointment.complete_and_invoice_appointment_command import (
    CompleteAndInvoiceAppointmentCommand,
)
from taller.application.schedule_reminder.schedule_reminder_command import ScheduleReminderCommand
from taller.models import Appointment, Client, Invoice, Order, Reminder


def part(name, spec="", qty=1, unit="ud"):
    return {"name": name, "spec": spec, "qty": qty, "unit": unit}


CLIENTS = [
    # nombre, teléfono (ficticio), chat de Telegram vinculado (ficticio) o None
    ("Marta Ferrer", "600 000 101", 111111111),
    ("Joan Mas", "600 000 102", None),
    ("Lucía Navarro", "600 000 103", None),
    ("Toni Pons", "600 000 104", None),
    ("Carmen Ruiz", "600 000 105", 222222222),
    ("Pedro Alonso", "600 000 106", None),
    ("Sofía Vidal", "600 000 107", None),
    ("Miguel Serra", "600 000 108", None),
]


def business_day(start, n):
    """El día laborable número n a partir de start (0 = start si es laborable, si no el siguiente)."""
    d = start
    while d.weekday() >= 5:
        d += timedelta(days=1)
    for _ in range(n):
        d += timedelta(days=1)
        while d.weekday() >= 5:
            d += timedelta(days=1)
    return d


def previous_business(start, n):
    d = start
    for _ in range(n):
        d -= timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
    return d


class Command(BaseCommand):
    help = "Carga datos de ejemplo (ficticios). Con --reset borra antes los datos del taller."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true",
                            help="borra clientes, citas, pedidos, avisos y facturas antes de cargar")
        parser.add_argument("--yes", action="store_true", help="no pedir confirmación")

    def handle(self, *args, **options):
        if Client.objects.exists():
            if not options["reset"]:
                raise CommandError("La agenda ya tiene datos. Usa --reset para borrarlos y cargar el ejemplo.")
            self.reset(options["yes"])
        self.load()

    # ------------------------------------------------------------------ borrar
    def reset(self, assume_yes):
        counts = {m.__name__: m.objects.count() for m in (Client, Appointment, Order, Reminder, Invoice)}
        resumen = ", ".join(f"{n}: {c}" for n, c in counts.items())
        if not assume_yes:
            answer = input(f"Se borrarán estos datos del taller ({resumen}). ¿Continuar? [s/N] ")
            if answer.strip().lower() not in ("s", "si", "sí", "y", "yes"):
                raise CommandError("Cancelado. No se ha borrado nada.")
        stamp = timezone.localtime().strftime("%Y%m%d-%H%M")
        out = StringIO()
        call_command("dumpdata", "taller", indent=2, stdout=out)
        backup = f"copia-antes-de-demo-{stamp}.json"
        with open(backup, "w", encoding="utf-8") as fh:
            fh.write(out.getvalue())
        self.stdout.write(f"Copia de seguridad guardada en {backup}")
        Reminder.objects.all().delete()
        Invoice.objects.all().delete()
        Order.objects.all().delete()
        Appointment.objects.all().delete()
        Client.objects.all().delete()
        self.stdout.write("Datos del taller borrados.")

    # ------------------------------------------------------------------ cargar
    def load(self):
        today = timezone.localdate()
        c = {}
        for name, phone, chat in CLIENTS:
            c[name] = Client.objects.create(name=name, phone=phone, telegram_chat_id=chat)

        def cita(client, day, plate, vehicle, note, service, parts, months=0, **extra):
            appt = Appointment.objects.create(
                client=c[client], date=day, plate=plate, vehicle=vehicle, note=note,
                service=service, parts=parts, repeat_months=months, **extra)
            if months:
                container.schedule_reminder_handler().handle(ScheduleReminderCommand(appointment_id=appt.pk))
            return appt

        # ---- ya hechas y facturadas (precios de recambios escritos como del albarán)
        done = [
            ("Marta Ferrer", previous_business(today, 15), "1234 BCD", "Seat Ibiza",
             "cambio aceite 5w30 seat ibiza", "cambio de aceite",
             [part("aceite motor", "5W30", 4, "L"), part("filtro de aceite")], 12,
             [Decimal("9.80"), Decimal("8.50")], Decimal("45")),
            ("Joan Mas", previous_business(today, 10), "2345 CDF", "Ford Focus",
             "itv ford focus", "ITV", [], 12, [], Decimal("30")),
            ("Lucía Navarro", previous_business(today, 6), "3456 DFG", "Renault Clio",
             "pastillas delanteras renault clio", "cambio de pastillas de freno",
             [part("pastillas de freno", "delanteras", 1, "juego")], 0, [Decimal("38.90")], Decimal("60")),
        ]
        for client, day, plate, vehicle, note, service, parts, months, prices, labor in done:
            appt = cita(client, day, plate, vehicle, note, service, parts, months, ordered=True)
            Order.objects.create(appointment=appt, supplier="email", parts=parts,
                                 detail="enviado por correo al distribuidor")
            inv = container.complete_and_invoice_handler().handle(CompleteAndInvoiceAppointmentCommand(
                appointment_id=appt.pk, part_prices=tuple(prices), labor=labor))
            Invoice.objects.filter(pk=inv.pk).update(created_at=day)

        # ---- próximos días
        d0, d1, d2, d3, d4 = (business_day(today, n) for n in range(5))
        cita("Miguel Serra", d0, "8901 KLM", "Kia Ceed", "itv kia ceed", "ITV", [], 12)
        cita("Sofía Vidal", d0, "7890 JKL", "Citroën C3", "correa distribucion citroen c3",
             "cambio de correa de distribución", [part("kit de distribución", "", 1, "kit")], 0)
        cita("Toni Pons", d1, "4567 FGH", "Volkswagen Golf", "neumaticos 4 michelin 205/55 vw golf",
             "cambio de neumáticos", [part("neumático", "205/55 R16 Michelin", 4)], 0)
        battery = cita("Carmen Ruiz", d1, "5678 GHJ", "Peugeot 208", "cambio bateria peugeot 208",
                       "cambio de batería", [part("batería", "", 1)], 0, ordered=True)
        Order.objects.create(appointment=battery, supplier="email", parts=battery.parts,
                             detail="enviado por correo al distribuidor")
        cita("Pedro Alonso", d1, "6789 HJK", "Opel Astra",
             "cambio de aceite 10w40 y filtros de aire y habitaculo opel astra",
             "cambio de aceite y filtros",
             [part("aceite motor", "10W40", 4, "L"), part("filtro de aceite"),
              part("filtro de aire"), part("filtro de habitáculo")], 12,
             order_error="el distribuidor no responde (tiempo agotado)")
        cita("Marta Ferrer", d2, "1234 BCD", "Seat Ibiza", "pastillas freno seat ibiza",
             "cambio de pastillas de freno", [part("pastillas de freno", "traseras", 1, "juego")], 0)
        cita("Joan Mas", d3, "2345 CDF", "Ford Focus", "cambio aceite 5w30 ford focus",
             "cambio de aceite", [part("aceite motor", "5W30", 5, "L"), part("filtro de aceite")], 12)
        cita("Lucía Navarro", d4, "3456 DFG", "Renault Clio", "cambio filtros aire y habitaculo renault clio",
             "cambio de filtros", [part("filtro de aire"), part("filtro de habitáculo")], 12)

        self.stdout.write(self.style.SUCCESS(
            f"Datos de ejemplo cargados: {Client.objects.count()} clientes, "
            f"{Appointment.objects.count()} citas, {Invoice.objects.count()} facturas."))
