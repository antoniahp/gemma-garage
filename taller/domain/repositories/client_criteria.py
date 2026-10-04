from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ClientCriteria:
    id: Optional[int] = None
    name_iexact: Optional[str] = None
    link_token: Optional[str] = None
