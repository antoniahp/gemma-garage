from taller.application.order_appointment_parts.order_appointment_parts_command_handler import (
    OrderAppointmentPartsCommandHandler,
)
from taller.domain.repositories.appointment_criteria import AppointmentCriteria
from taller.domain.repositories.appointment_repository import AppointmentRepository

from taller.application.review_parts_order.review_parts_order_command import ReviewPartsOrderCommand


class ReviewPartsOrderCommandHandler:
    def __init__(self, appointment_repository: AppointmentRepository,
                 order_handler: OrderAppointmentPartsCommandHandler):
        self.appointment_repository = appointment_repository
        self.order_handler = order_handler

    def handle(self, command: ReviewPartsOrderCommand) -> dict:
        """Guarda los recambios corregidos y, si se pide, envía los pedidos marcados.

        Devuelve {"sent": n, "errors": ["Cliente: no se pudo pedir (...)", ...]}.
        """
        pending = {
            a.pk: a for a in self.appointment_repository.find_by_criteria(AppointmentCriteria(
                ids=tuple(command.appointment_ids), status="pendiente", ordered=False))
        }
        for pk, appointment in pending.items():
            parts = command.parts_by_appointment.get(pk, appointment.parts)
            if parts != appointment.parts:
                appointment.parts = parts
                self.appointment_repository.update_parts(pk, parts)
        sent, errors = 0, []
        if command.send:
            for pk in command.send_ids:
                appointment = pending.get(pk)
                if appointment is None or not appointment.parts:
                    continue
                try:
                    self.order_handler.order(appointment)
                    sent += 1
                except Exception as exc:
                    errors.append(f"{appointment.client.name}: no se pudo pedir ({exc}).")
        return {"sent": sent, "errors": errors}
