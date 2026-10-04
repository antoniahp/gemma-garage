from abc import ABC, abstractmethod

from taller.domain.client import Client
from taller.domain.repositories.client_criteria import ClientCriteria


class ClientRepository(ABC):
    @abstractmethod
    def save(self, client: Client) -> None:
        raise NotImplementedError

    @abstractmethod
    def find_by_criteria(self, criteria: ClientCriteria) -> list[Client]:
        raise NotImplementedError

    @abstractmethod
    def find_with_activity(self, text: str) -> list[Client]:
        """Clientes con `visits` (citas) y `waiting` (avisos sin enviar); filtra por nombre o teléfono."""
        raise NotImplementedError

    @abstractmethod
    def find_names(self) -> list[str]:
        raise NotImplementedError
