from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class AppointmentCriteria:
    id: Optional[int] = None
    ids: Optional[tuple] = None
    date: Optional[date] = None
    date_gte: Optional[date] = None
    date_lte: Optional[date] = None
    date_lt: Optional[date] = None
    status: Optional[str] = None
    ordered: Optional[bool] = None
    with_order_error: Optional[bool] = None
