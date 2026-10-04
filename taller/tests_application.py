"""Tests de los casos de uso con puertos falsos en memoria (sin Ollama, sin Telegram, sin repositorios reales).

Es lo que permite la arquitectura hexagonal: la lógica se prueba sin tocar la infraestructura.
"""

from datetime import date
from unittest import mock

from django.test import SimpleTestCase, TestCase

from taller.application.order_appointment_parts.order_appointment_parts_command_handler import (
    OrderAppointmentPartsCommandHandler,
)
from taller.application.run_daily.run_daily_command import RunDailyCommand
from taller.application.run_daily.run_daily_command_handler import RunDailyCommandHandler
from taller.domain.appointment import Appointment
from taller.domain.client import Client
from taller.domain.client_notifier import ClientNotifier
from taller.domain.note_parser import NoteParser, NoteParserUnavailableException
from taller.domain.parsed_note import ParsedNote
from taller.domain.parts_supplier import PartsSupplier
from taller.domain.reminder import Reminder
from taller.domain.repositories.appointment_repository import AppointmentRepository
from taller.domain.repositories.order_repository import OrderRepository
from taller.domain.repositories.reminder_repository import ReminderRepository
from taller.infrastructure.note_parser_with_fallback import NoteParserWithFallback
from taller.infrastructure.rules_note_parser import RulesNoteParser


class MemoryAppointments(AppointmentRepository):
    def __init__(self, appointments):
        self.items = {a.pk: a for a in appointments}
        self.errors = {}

    def save(self, appointment): self.items[appointment.pk] = appointment
    def find_or_fail_by_id(self, id): return self.items[id]
    def find_by_plate(self, normalized_plate, limit): return []
    def search(self, text, limit): return []
    def update_parts(self, id, parts): self.items[id].parts = parts
    def mark_done(self, id): self.items[id].status = "hecha"

    def find_by_criteria(self, criteria):
        return [a for a in self.items.values()
                if (criteria.ordered is None or a.ordered == criteria.ordered)
                and (criteria.status is None or a.status == criteria.status)
                and (criteria.date_gte is None or a.date >= criteria.date_gte)]

    def mark_ordered(self, id):
        self.items[id].ordered = True
        self.items[id].order_error = ""

    def record_order_error(self, id, message):
        self.items[id].order_error = message


class MemoryReminders(ReminderRepository):
    def __init__(self, reminders):
        self.items = list(reminders)
        self.sent = {}

    def save(self, reminder): self.items.append(reminder)
    def delete_unsent_of_appointment(self, appointment_id): pass

    def find_by_criteria(self, criteria, limit=None):
        return [r for r in self.items if not r.pk in self.sent and r.send_on <= criteria.send_on_lte]

    def mark_sent(self, id, detail): self.sent[id] = detail


class MemoryOrders(OrderRepository):
    def __init__(self): self.saved = []
    def save(self, order): self.saved.append(order)


class FakeSupplier(PartsSupplier):
    name = "fake"

    def __init__(self, fail=False):
        self.fail, self.orders = fail, []

    def send_order(self, order):
        if self.fail:
            raise RuntimeError("el distribuidor no responde")
        self.orders.append(order)
        return "ok"


class FakeNotifier(ClientNotifier):
    def __init__(self): self.to_owner, self.to_clients = [], []

    def notify_owner(self, text):
        self.to_owner.append(text)
        return True, "ok"

    def notify_client(self, client, text):
        self.to_clients.append((client.name, text))
        return True, "ok"


def appointment(pk, day, parts=True):
    client = Client(name="Ana", phone="600")
    return Appointment(
        pk=pk, client=client, date=day, service="cambio de aceite", plate="1234ABC",
        parts=[{"name": "aceite motor", "spec": "5W30", "qty": 4, "unit": "L"}] if parts else [],
    )


class RunDailyConPuertosFalsosTests(TestCase):
    def handler(self, appointments, reminders=(), supplier=None):
        self.appts, self.reminders = MemoryAppointments(appointments), MemoryReminders(reminders)
        self.orders, self.supplier = MemoryOrders(), supplier or FakeSupplier()
        self.notifier = FakeNotifier()
        order = OrderAppointmentPartsCommandHandler(self.appts, self.orders, self.supplier)
        return RunDailyCommandHandler(self.appts, self.reminders, order, self.notifier)

    def test_pide_el_dia_laborable_anterior(self):
        h = self.handler([appointment(1, date(2026, 10, 6))])           # cita el martes
        self.assertEqual(h.handle(RunDailyCommand(today=date(2026, 10, 3)))["orders"], [])  # sábado
        report = h.handle(RunDailyCommand(today=date(2026, 10, 5)))                          # lunes
        self.assertEqual([o["appointment_id"] for o in report["orders"]], [1])
        self.assertEqual(self.supplier.orders[0]["deliver_on"], "2026-10-06")
        self.assertTrue(self.appts.items[1].ordered)
        self.assertEqual(h.handle(RunDailyCommand(today=date(2026, 10, 5)))["orders"], [])   # no duplica

    def test_un_fallo_del_proveedor_se_anota_y_no_marca_pedido(self):
        h = self.handler([appointment(1, date(2026, 10, 6))], supplier=FakeSupplier(fail=True))
        report = h.handle(RunDailyCommand(today=date(2026, 10, 5)))
        self.assertEqual(len(report["errors"]), 1)
        self.assertFalse(self.appts.items[1].ordered)
        self.assertIn("no responde", self.appts.items[1].order_error)

    def test_envia_los_avisos_y_resume_al_mecanico(self):
        reminder = Reminder(pk=7, client=Client(name="Ana"), send_on=date(2027, 9, 29), message="Hola")
        h = self.handler([], reminders=[reminder])
        report = h.handle(RunDailyCommand(today=date(2027, 9, 29)))
        self.assertEqual(len(report["reminders"]), 1)
        self.assertEqual(self.notifier.to_clients, [("Ana", "Hola")])
        self.assertIn("Avisos enviados: 1", self.notifier.to_owner[0])


class IntérpreteConRespaldoTests(SimpleTestCase):
    def test_si_gemma_no_responde_se_usan_las_reglas_y_se_explica_por_que(self):
        primary = mock.Mock(spec=NoteParser)
        primary.parse.side_effect = NoteParserUnavailableException("Ollama apagado")
        result = NoteParserWithFallback(primary, RulesNoteParser()).parse("ITV seat leon")
        self.assertEqual(result.service, "ITV")
        self.assertEqual(result.engine, "reglas")
        self.assertEqual(result.llm_error, "Ollama apagado")

    def test_si_gemma_responde_se_usa_su_resultado(self):
        primary = mock.Mock(spec=NoteParser)
        primary.parse.return_value = ParsedNote("cambio de aceite", "Opel", 12, [], engine="ollama:gemma3")
        fallback = mock.Mock(spec=NoteParser)
        result = NoteParserWithFallback(primary, fallback).parse("aceite opel")
        self.assertEqual(result.engine, "ollama:gemma3")
        fallback.parse.assert_not_called()
