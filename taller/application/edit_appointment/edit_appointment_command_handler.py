from taller.application.schedule_reminder.schedule_reminder_command import ScheduleReminderCommand
from taller.application.schedule_reminder.schedule_reminder_command_handler import (
    ScheduleReminderCommandHandler,
)
from taller.domain.appointment import Appointment
from taller.domain.client import Client
from taller.domain.note_parser import NoteParser
from taller.domain.repositories.appointment_repository import AppointmentRepository
from taller.domain.repositories.client_criteria import ClientCriteria
from taller.domain.repositories.client_repository import ClientRepository
from taller.domain.repositories.reminder_repository import ReminderRepository

from taller.application.edit_appointment.edit_appointment_command import EditAppointmentCommand


class EditAppointmentCommandHandler:
    def __init__(self, client_repository: ClientRepository, appointment_repository: AppointmentRepository,
                 reminder_repository: ReminderRepository, note_parser: NoteParser,
                 schedule_reminder: ScheduleReminderCommandHandler):
        self.client_repository = client_repository
        self.appointment_repository = appointment_repository
        self.reminder_repository = reminder_repository
        self.note_parser = note_parser
        self.schedule_reminder = schedule_reminder

    def handle(self, command: EditAppointmentCommand) -> Appointment:
        """Guarda los cambios de una cita. Si cambia la fecha o la repetición, reprograma el aviso."""
        appointment = self.appointment_repository.find_or_fail_by_id(command.appointment_id)
        client = self.client_repository.find_by_criteria(ClientCriteria(name_iexact=command.client_name))
        client = client[0] if client else Client(name=command.client_name)
        if command.phone and client.phone != command.phone:
            client.phone = command.phone
        self.client_repository.save(client)

        previous = (appointment.date, appointment.repeat_months)
        appointment.client, appointment.date = client, command.date
        appointment.plate, appointment.note, appointment.vehicle = command.plate, command.note, command.vehicle
        if command.reinterpret:
            self._interpret(appointment)
        else:
            appointment.service = command.service
            appointment.repeat_months = command.repeat_months or 0
            appointment.parts = list(command.parts)
            if not appointment.service and appointment.note:
                self._interpret(appointment)
        self.appointment_repository.save(appointment)

        if (appointment.date, appointment.repeat_months) != previous:
            self.reminder_repository.delete_unsent_of_appointment(appointment.pk)
            if appointment.repeat_months:
                self.schedule_reminder.handle(ScheduleReminderCommand(appointment_id=appointment.pk))
        return appointment

    def _interpret(self, appointment):
        parsed = self.note_parser.parse(appointment.note, vehicle=appointment.vehicle)
        appointment.service, appointment.vehicle = parsed.service, parsed.vehicle
        appointment.parts, appointment.repeat_months = parsed.parts, parsed.repeat_months
