from taller.domain.appointment import Appointment
from taller.domain.repositories.appointment_repository import AppointmentRepository

from taller.application.search_appointments.search_appointments_query import SearchAppointmentsQuery


class SearchAppointmentsQueryHandler:
    def __init__(self, appointment_repository: AppointmentRepository):
        self.appointment_repository = appointment_repository

    def handle(self, query: SearchAppointmentsQuery) -> list[Appointment]:
        text = query.text.strip()
        return self.appointment_repository.search(text, limit=60) if text else []
