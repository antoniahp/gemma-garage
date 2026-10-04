from dataclasses import dataclass


@dataclass(frozen=True)
class ReviewPartsOrderCommand:
    appointment_ids: tuple
    parts_by_appointment: dict
    send_ids: tuple = ()
    send: bool = False
