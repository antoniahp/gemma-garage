from dataclasses import dataclass


@dataclass(frozen=True)
class InterpretNoteQuery:
    note: str
    vehicle: str = ""
