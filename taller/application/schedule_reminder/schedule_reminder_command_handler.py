from datetime import timedelta

from taller.domain.business_calendar import add_months
from taller.domain.reminder import Reminder
from taller.domain.repositories.appointment_repository import AppointmentRepository
from taller.domain.repositories.reminder_repository import ReminderRepository

from taller.application.schedule_reminder.schedule_reminder_command import ScheduleReminderCommand


class ScheduleReminderCommandHandler:
    def __init__(self, appointment_repository: AppointmentRepository,
                 reminder_repository: ReminderRepository):
        self.appointment_repository = appointment_repository
        self.reminder_repository = reminder_repository

    def handle(self, command: ScheduleReminderCommand) -> Reminder:
        """Programa el aviso para una semana antes de que se cumpla el plazo de la cita."""
        appointment = self.appointment_repository.find_or_fail_by_id(command.appointment_id)
        next_date = add_months(appointment.date, appointment.repeat_months)
        plate = f" ({appointment.plate})" if appointment.plate else ""
        message = (
            f"Hola {appointment.client.name}, desde el taller le recordamos que a su vehículo"
            f"{plate} le toca {appointment.service} sobre el {next_date.strftime('%d/%m/%Y')}. "
            f"Llámenos y le damos cita."
        )
        reminder = Reminder(
            client=appointment.client, appointment=appointment,
            send_on=next_date - timedelta(days=7), message=message,
        )
        self.reminder_repository.save(reminder)
        return reminder
