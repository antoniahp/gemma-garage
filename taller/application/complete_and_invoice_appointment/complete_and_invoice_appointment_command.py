from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CompleteAndInvoiceAppointmentCommand:
    appointment_id: int
    part_prices: tuple = ()
    labor: Decimal | None = None
    extras: tuple = ()
