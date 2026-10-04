from taller.domain.appointment import Appointment
from taller.domain.repositories.appointment_repository import AppointmentRepository

from taller.application.find_appointment.find_appointment_query import FindAppointmentQuery


class FindAppointmentQueryHandler:
    def __init__(self, appointment_repository: AppointmentRepository):
        self.appointment_repository = appointment_repository

    def handle(self, query: FindAppointmentQuery) -> Appointment:
        return self.appointment_repository.find_or_fail_by_id(query.appointment_id)
