from datetime import timedelta

from taller.domain.repositories.appointment_criteria import AppointmentCriteria
from taller.domain.repositories.appointment_repository import AppointmentRepository
from taller.domain.repositories.client_repository import ClientRepository
from taller.domain.repositories.reminder_criteria import ReminderCriteria
from taller.domain.repositories.reminder_repository import ReminderRepository

from taller.application.find_home_board.find_home_board_query import FindHomeBoardQuery


class FindHomeBoardQueryHandler:
    def __init__(self, appointment_repository: AppointmentRepository,
                 reminder_repository: ReminderRepository, client_repository: ClientRepository):
        self.appointment_repository = appointment_repository
        self.reminder_repository = reminder_repository
        self.client_repository = client_repository

    def handle(self, query: FindHomeBoardQuery) -> dict:
        """Lo que se ve en la pantalla Hoy."""
        today = query.today
        tomorrow = today + timedelta(days=1)
        find = self.appointment_repository.find_by_criteria
        todo = find(AppointmentCriteria(status="pendiente"))
        return {
            "today_list": find(AppointmentCriteria(date=today)),
            "tomorrow_list": find(AppointmentCriteria(date=tomorrow)),
            "late_list": [a for a in todo if a.date < today],
            "to_order": [a for a in todo if not a.ordered and a.date >= today
                         and a.order_state == "pedir_hoy"],
            "failed": len([a for a in todo if not a.ordered and a.order_error]),
            "reminders": self.reminder_repository.find_by_criteria(ReminderCriteria(sent=False), limit=5),
            "clients": self.client_repository.find_names(),
        }
