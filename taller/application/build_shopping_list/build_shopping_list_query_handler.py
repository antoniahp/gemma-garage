from taller.domain.parts import shopping_list
from taller.domain.repositories.appointment_criteria import AppointmentCriteria
from taller.domain.repositories.appointment_repository import AppointmentRepository

from taller.application.build_shopping_list.build_shopping_list_query import BuildShoppingListQuery


class BuildShoppingListQueryHandler:
    def __init__(self, appointment_repository: AppointmentRepository):
        self.appointment_repository = appointment_repository

    def handle(self, query: BuildShoppingListQuery) -> dict:
        """Todos los recambios de un día, sumados."""
        appointments = self.appointment_repository.find_by_criteria(
            AppointmentCriteria(date=query.day, status="pendiente"))
        return {"rows": shopping_list(appointments), "appointments": appointments}
