from dataclasses import dataclass


@dataclass(frozen=True)
class FindPlateHistoryQuery:
    plate: str
