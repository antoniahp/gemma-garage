from abc import ABC, abstractmethod


class ClientNotifier(ABC):
    """Avisa a clientes y al mecánico. Devuelve (ok, detalle) y nunca lanza por un fallo de red."""

    @abstractmethod
    def notify_owner(self, text: str) -> tuple[bool, str]:
        raise NotImplementedError

    @abstractmethod
    def notify_client(self, client, text: str) -> tuple[bool, str]:
        raise NotImplementedError
