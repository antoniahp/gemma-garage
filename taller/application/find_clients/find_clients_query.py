from dataclasses import dataclass


@dataclass(frozen=True)
class FindClientsQuery:
    text: str = ""
