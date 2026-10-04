from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class BuildShoppingListQuery:
    day: date
