from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParsedNote:
    """Lo que se ha entendido de la nota del mecánico."""

    service: str
    vehicle: str
    repeat_months: int
    parts: list = field(default_factory=list)
    engine: str = "reglas"
    llm_error: str = ""
