from taller.domain.parts import describe_parts
from taller.domain.plate import normalize_plate
from taller.domain.repositories.appointment_repository import AppointmentRepository

from taller.application.find_plate_history.find_plate_history_query import FindPlateHistoryQuery


class FindPlateHistoryQueryHandler:
    def __init__(self, appointment_repository: AppointmentRepository):
        self.appointment_repository = appointment_repository

    def handle(self, query: FindPlateHistoryQuery) -> dict:
        """Visitas anteriores de una matrícula. {"found": False} si no hay (o es demasiado corta)."""
        plate = normalize_plate(query.plate)
        if len(plate) < 4:
            return {"found": False}
        rows = self.appointment_repository.find_by_plate(plate, limit=5)
        if not rows:
            return {"found": False}
        last = rows[0]
        return {
            "found": True, "client": last.client.name, "phone": last.client.phone,
            "vehicle": last.vehicle,
            "visits": [{
                "date": a.date.strftime("%d/%m/%Y"), "service": a.service or a.note,
                "parts": describe_parts(a.parts),
            } for a in rows],
        }
