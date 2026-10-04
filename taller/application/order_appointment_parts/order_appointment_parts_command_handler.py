from django.db import transaction

from taller.domain.appointment import Appointment
from taller.domain.order import Order
from taller.domain.parts_supplier import PartsSupplier
from taller.domain.repositories.appointment_repository import AppointmentRepository
from taller.domain.repositories.order_repository import OrderRepository

from taller.application.order_appointment_parts.order_appointment_parts_command import OrderAppointmentPartsCommand


class OrderAppointmentPartsCommandHandler:
    def __init__(self, appointment_repository: AppointmentRepository, order_repository: OrderRepository,
                 parts_supplier: PartsSupplier):
        self.appointment_repository = appointment_repository
        self.order_repository = order_repository
        self.parts_supplier = parts_supplier

    def handle(self, command: OrderAppointmentPartsCommand) -> str:
        appointment = self.appointment_repository.find_or_fail_by_id(command.appointment_id)
        return self.order(appointment)

    def order(self, appointment: Appointment) -> str:
        """Envía el pedido de una cita. Lanza excepción si el proveedor falla (y deja anotado el motivo)."""
        order = {
            "appointment_id": appointment.pk,
            "deliver_on": appointment.date.isoformat(),
            "service": appointment.service,
            "vehicle": appointment.vehicle,
            "plate": appointment.plate,
            "parts": appointment.parts,
        }
        try:
            detail = self.parts_supplier.send_order(order)
        except Exception as exc:
            self.appointment_repository.record_order_error(appointment.pk, str(exc))
            raise
        with transaction.atomic():
            self.order_repository.save(Order(
                appointment=appointment, supplier=self.parts_supplier.name,
                parts=appointment.parts, detail=detail,
            ))
            self.appointment_repository.mark_ordered(appointment.pk)
        return detail
