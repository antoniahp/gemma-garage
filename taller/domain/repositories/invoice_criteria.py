from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class InvoiceCriteria:
    appointment_id: Optional[int] = None
