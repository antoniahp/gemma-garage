from dataclasses import dataclass


@dataclass(frozen=True)
class SearchAppointmentsQuery:
    text: str
