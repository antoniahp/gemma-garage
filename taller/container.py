"""Raíz de composición: aquí (y solo aquí) se eligen los adaptadores que usa cada caso de uso.

Las vistas, el admin y los comandos de gestión piden los handlers a estas funciones; los casos de
uso solo conocen los puertos del dominio. Para cambiar de proveedor de recambios, de intérprete de
notas o de canal de avisos se cambia una función de este archivo.
"""

from django.conf import settings

from taller.application.build_shopping_list.build_shopping_list_query_handler import (
    BuildShoppingListQueryHandler,
)
from taller.application.complete_and_invoice_appointment.complete_and_invoice_appointment_command_handler import (
    CompleteAndInvoiceAppointmentCommandHandler,
)
from taller.application.create_appointment.create_appointment_command_handler import (
    CreateAppointmentCommandHandler,
)
from taller.application.edit_appointment.edit_appointment_command_handler import (
    EditAppointmentCommandHandler,
)
from taller.application.find_appointment.find_appointment_query_handler import FindAppointmentQueryHandler
from taller.application.find_clients.find_clients_query_handler import FindClientsQueryHandler
from taller.application.find_home_board.find_home_board_query_handler import FindHomeBoardQueryHandler
from taller.application.find_invoice.find_invoice_query_handler import FindInvoiceQueryHandler
from taller.application.find_invoices.find_invoices_query_handler import FindInvoicesQueryHandler
from taller.application.find_labor_price.find_labor_price_query_handler import FindLaborPriceQueryHandler
from taller.application.find_labor_rates.find_labor_rates_query_handler import FindLaborRatesQueryHandler
from taller.application.find_order_review.find_order_review_query_handler import FindOrderReviewQueryHandler
from taller.application.find_plate_history.find_plate_history_query_handler import (
    FindPlateHistoryQueryHandler,
)
from taller.application.find_week.find_week_query_handler import FindWeekQueryHandler
from taller.application.interpret_note.interpret_note_query_handler import InterpretNoteQueryHandler
from taller.application.order_appointment_parts.order_appointment_parts_command_handler import (
    OrderAppointmentPartsCommandHandler,
)
from taller.application.process_telegram_update.process_telegram_update_command_handler import (
    ProcessTelegramUpdateCommandHandler,
)
from taller.application.review_parts_order.review_parts_order_command_handler import (
    ReviewPartsOrderCommandHandler,
)
from taller.application.run_daily.run_daily_command_handler import RunDailyCommandHandler
from taller.application.save_labor_rates.save_labor_rates_command_handler import (
    SaveLaborRatesCommandHandler,
)
from taller.application.schedule_reminder.schedule_reminder_command_handler import (
    ScheduleReminderCommandHandler,
)
from taller.application.search_appointments.search_appointments_query_handler import (
    SearchAppointmentsQueryHandler,
)
from taller.infrastructure import telegram_api
from taller.infrastructure.email_parts_supplier import EmailPartsSupplier
from taller.infrastructure.note_parser_with_fallback import NoteParserWithFallback
from taller.infrastructure.ollama_note_parser import OllamaNoteParser
from taller.infrastructure.outbox_client_notifier import OutboxClientNotifier
from taller.infrastructure.outbox_parts_supplier import OutboxPartsSupplier
from taller.infrastructure.repositories.db_appointment_repository import DbAppointmentRepository
from taller.infrastructure.repositories.db_client_repository import DbClientRepository
from taller.infrastructure.repositories.db_invoice_repository import DbInvoiceRepository
from taller.infrastructure.repositories.db_labor_rate_repository import DbLaborRateRepository
from taller.infrastructure.repositories.db_order_repository import DbOrderRepository
from taller.infrastructure.repositories.db_reminder_repository import DbReminderRepository
from taller.infrastructure.rules_note_parser import RulesNoteParser
from taller.infrastructure.telegram_client_notifier import TelegramClientNotifier


# ---------------------------------------------------------------- puertos -> adaptadores

def note_parser():
    """Gemma (Ollama) si responde; si no, reglas simples."""
    return NoteParserWithFallback(primary=OllamaNoteParser(), fallback=RulesNoteParser())


def parts_supplier():
    return EmailPartsSupplier() if settings.TALLER_SUPPLIER == "email" else OutboxPartsSupplier()


def client_notifier():
    return TelegramClientNotifier() if telegram_api.configured() else OutboxClientNotifier()


def _reply_telegram(chat_id, text):
    telegram_api.send(chat_id, text)  # se busca en el momento de usarlo (así se puede sustituir en tests)


# ---------------------------------------------------------------- casos de uso

def schedule_reminder_handler():
    return ScheduleReminderCommandHandler(DbAppointmentRepository(), DbReminderRepository())


def create_appointment_handler():
    return CreateAppointmentCommandHandler(
        DbClientRepository(), DbAppointmentRepository(), note_parser(), schedule_reminder_handler())


def edit_appointment_handler():
    return EditAppointmentCommandHandler(
        DbClientRepository(), DbAppointmentRepository(), DbReminderRepository(), note_parser(),
        schedule_reminder_handler())


def order_appointment_parts_handler():
    return OrderAppointmentPartsCommandHandler(DbAppointmentRepository(), DbOrderRepository(), parts_supplier())


def review_parts_order_handler():
    return ReviewPartsOrderCommandHandler(DbAppointmentRepository(), order_appointment_parts_handler())


def run_daily_handler():
    return RunDailyCommandHandler(
        DbAppointmentRepository(), DbReminderRepository(), order_appointment_parts_handler(), client_notifier())


def find_labor_price_handler():
    return FindLaborPriceQueryHandler(DbLaborRateRepository())


def complete_and_invoice_handler():
    return CompleteAndInvoiceAppointmentCommandHandler(
        DbAppointmentRepository(), DbInvoiceRepository(), find_labor_price_handler())


def save_labor_rates_handler():
    return SaveLaborRatesCommandHandler(DbLaborRateRepository())


def process_telegram_update_handler():
    return ProcessTelegramUpdateCommandHandler(DbClientRepository(), _reply_telegram)


def interpret_note_handler():
    return InterpretNoteQueryHandler(note_parser())


def find_appointment_handler():
    return FindAppointmentQueryHandler(DbAppointmentRepository())


def find_invoice_handler():
    return FindInvoiceQueryHandler(DbInvoiceRepository())


def find_invoices_handler():
    return FindInvoicesQueryHandler(DbInvoiceRepository())


def find_clients_handler():
    return FindClientsQueryHandler(DbClientRepository())


def find_home_board_handler():
    return FindHomeBoardQueryHandler(DbAppointmentRepository(), DbReminderRepository(), DbClientRepository())


def find_week_handler():
    return FindWeekQueryHandler(DbAppointmentRepository())


def find_order_review_handler():
    return FindOrderReviewQueryHandler(DbAppointmentRepository())


def build_shopping_list_handler():
    return BuildShoppingListQueryHandler(DbAppointmentRepository())


def find_plate_history_handler():
    return FindPlateHistoryQueryHandler(DbAppointmentRepository())


def search_appointments_handler():
    return SearchAppointmentsQueryHandler(DbAppointmentRepository())


def find_labor_rates_handler():
    return FindLaborRatesQueryHandler(DbLaborRateRepository())
