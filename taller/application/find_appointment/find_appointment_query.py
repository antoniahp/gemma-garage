from dataclasses import dataclass


@dataclass(frozen=True)
class FindAppointmentQuery:
    appointment_id: int
