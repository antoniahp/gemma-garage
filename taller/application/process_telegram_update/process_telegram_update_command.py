from dataclasses import dataclass


@dataclass(frozen=True)
class ProcessTelegramUpdateCommand:
    update: dict
