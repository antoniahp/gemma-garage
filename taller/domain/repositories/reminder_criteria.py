from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class ReminderCriteria:
    appointment_id: Optional[int] = None
    sent: Optional[bool] = None
    send_on_lte: Optional[date] = None
