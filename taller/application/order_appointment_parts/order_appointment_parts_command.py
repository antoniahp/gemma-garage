from dataclasses import dataclass


@dataclass(frozen=True)
class OrderAppointmentPartsCommand:
    appointment_id: int
