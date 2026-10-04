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

from taller.application.create_appointment.create_appointment_command import CreateAppointmentCommand


class CreateAppointmentCommandHandler:
    def __init__(self, client_repository: ClientRepository, appointment_repository: AppointmentRepository,
                 note_parser: NoteParser, schedule_reminder: ScheduleReminderCommandHandler):
        self.client_repository = client_repository
        self.appointment_repository = appointment_repository
        self.note_parser = note_parser
        self.schedule_reminder = schedule_reminder

    def handle(self, command: CreateAppointmentCommand) -> Appointment:
        client = self.client_repository.find_by_criteria(
            ClientCriteria(name_iexact=command.client_name)
        )
        if client:
            client = client[0]
            if command.phone and not client.phone:
                client.phone = command.phone
                self.client_repository.save(client)
        else:
            client = Client(name=command.client_name, phone=command.phone)
            self.client_repository.save(client)

        parsed = self.note_parser.parse(command.note, vehicle=command.vehicle)
        appointment = Appointment(
            client=client, date=command.date, plate=command.plate, note=command.note,
            service=parsed.service, vehicle=parsed.vehicle, parts=parsed.parts,
            repeat_months=parsed.repeat_months,
        )
        self.appointment_repository.save(appointment)
        if appointment.repeat_months:
            self.schedule_reminder.handle(ScheduleReminderCommand(appointment_id=appointment.pk))
        return appointment
