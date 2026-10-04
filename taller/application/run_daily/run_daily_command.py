from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class RunDailyCommand:
    today: date | None = None
