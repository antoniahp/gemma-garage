from dataclasses import dataclass


@dataclass(frozen=True)
class FindInvoiceQuery:
    appointment_id: int
