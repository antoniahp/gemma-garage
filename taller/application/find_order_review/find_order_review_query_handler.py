from datetime import timedelta

from taller.domain.repositories.appointment_criteria import AppointmentCriteria
from taller.domain.repositories.appointment_repository import AppointmentRepository

from taller.application.find_order_review.find_order_review_query import FindOrderReviewQuery


class FindOrderReviewQueryHandler:
    def __init__(self, appointment_repository: AppointmentRepository):
        self.appointment_repository = appointment_repository

    def handle(self, query: FindOrderReviewQuery) -> list[dict]:
        """Citas con recambios por pedir (próximos 7 días), con las que tocan pedir ya marcadas."""
        appointments = self.appointment_repository.find_by_criteria(AppointmentCriteria(
            status="pendiente", ordered=False, date_gte=query.today,
            date_lte=query.today + timedelta(days=7)))
        rows = [{"a": a, "checked": bool(a.parts) and a.order_state in ("pedir_hoy", "fallo")}
                for a in appointments]
        rows.sort(key=lambda r: (not r["checked"], r["a"].date))
        return rows
