from dataclasses import dataclass


@dataclass(frozen=True)
class FindLaborPriceQuery:
    service: str
