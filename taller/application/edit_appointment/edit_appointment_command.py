from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class EditAppointmentCommand:
    appointment_id: int
    date: date
    client_name: str
    note: str
    phone: str = ""
    plate: str = ""
    vehicle: str = ""
    service: str = ""
    repeat_months: int = 0
    parts: tuple = ()
    reinterpret: bool = False
