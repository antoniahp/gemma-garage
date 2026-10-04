from django.utils import timezone

from taller.application.order_appointment_parts.order_appointment_parts_command_handler import (
    OrderAppointmentPartsCommandHandler,
)
from taller.domain.business_calendar import previous_business_day
from taller.domain.client_notifier import ClientNotifier
from taller.domain.repositories.appointment_criteria import AppointmentCriteria
from taller.domain.repositories.appointment_repository import AppointmentRepository
from taller.domain.repositories.reminder_criteria import ReminderCriteria
from taller.domain.repositories.reminder_repository import ReminderRepository

from taller.application.run_daily.run_daily_command import RunDailyCommand


class RunDailyCommandHandler:
    def __init__(self, appointment_repository: AppointmentRepository, reminder_repository: ReminderRepository,
                 order_handler: OrderAppointmentPartsCommandHandler, notifier: ClientNotifier):
        self.appointment_repository = appointment_repository
        self.reminder_repository = reminder_repository
        self.order_handler = order_handler
        self.notifier = notifier

    def handle(self, command: RunDailyCommand) -> dict:
        """Tarea diaria: pide los recambios que toquen y envía los avisos pendientes.

        Se pide el día laborable anterior a la cita. Si un día no se ejecutó, la siguiente
        ejecución pide igualmente lo que falte. Nunca duplica pedidos.
        """
        today = command.today or timezone.localdate()
        report = {"orders": [], "reminders": [], "errors": []}

        pending = self.appointment_repository.find_by_criteria(
            AppointmentCriteria(ordered=False, status="pendiente", date_gte=today)
        )
        for appointment in pending:
            if previous_business_day(appointment.date) > today or not appointment.parts:
                continue
            try:
                detail = self.order_handler.order(appointment)
            except Exception as exc:  # si falla, no se marca como pedido y se reintenta
                report["errors"].append(f"pedido cita {appointment.pk}: {exc}")
                continue
            report["orders"].append({"appointment_id": appointment.pk, "detail": detail})

        due = self.reminder_repository.find_by_criteria(ReminderCriteria(sent=False, send_on_lte=today))
        for reminder in due:
            ok, detail = self.notifier.notify_client(reminder.client, reminder.message)
            if ok:
                self.reminder_repository.mark_sent(reminder.pk, detail)
                report["reminders"].append({"reminder_id": reminder.pk, "detail": detail})
            else:
                report["errors"].append(f"aviso {reminder.pk}: {detail}")

        if report["orders"] or report["reminders"]:
            lines = [f"Resumen del {today.strftime('%d/%m/%Y')}:"]
            lines += [f"- Recambios pedidos para la cita {o['appointment_id']}" for o in report["orders"]]
            lines += [f"- Avisos enviados: {len(report['reminders'])}"] if report["reminders"] else []
            self.notifier.notify_owner("\n".join(lines))
        return report
