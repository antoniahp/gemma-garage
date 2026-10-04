from datetime import timedelta

from taller.domain.repositories.appointment_criteria import AppointmentCriteria
from taller.domain.repositories.appointment_repository import AppointmentRepository

from taller.application.find_week.find_week_query import FindWeekQuery


class FindWeekQueryHandler:
    def __init__(self, appointment_repository: AppointmentRepository):
        self.appointment_repository = appointment_repository

    def handle(self, query: FindWeekQuery) -> dict:
        start = query.reference - timedelta(days=query.reference.weekday())
        days = []
        for i in range(7):
            d = start + timedelta(days=i)
            days.append({
                "date": d, "is_today": d == query.today, "weekend": d.weekday() >= 5,
                "items": self.appointment_repository.find_by_criteria(AppointmentCriteria(date=d)),
            })
        return {"days": days, "start": start, "end": start + timedelta(days=6),
                "prev": start - timedelta(days=7), "next": start + timedelta(days=7)}
