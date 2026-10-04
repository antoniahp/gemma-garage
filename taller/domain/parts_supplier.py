from abc import ABC, abstractmethod


class PartsSupplier(ABC):
    name: str

    @abstractmethod
    def send_order(self, order: dict) -> str:
        """Envía el pedido y devuelve un detalle legible. Lanza una excepción si falla."""
        raise NotImplementedError
