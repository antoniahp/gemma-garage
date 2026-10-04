from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class CreateAppointmentCommand:
    date: date
    client_name: str
    note: str
    phone: str = ""
    plate: str = ""
    vehicle: str = ""
