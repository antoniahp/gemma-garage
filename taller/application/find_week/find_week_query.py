from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class FindWeekQuery:
    reference: date
    today: date
