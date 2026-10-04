from taller.domain.parts_supplier import PartsSupplier
from taller.infrastructure import outbox


class OutboxPartsSupplier(PartsSupplier):
    """Modo prueba: guarda el pedido en outbox/pedidos.jsonl."""

    name = "outbox"

    def send_order(self, order: dict) -> str:
        outbox.append("pedidos.jsonl", order)
        return "guardado en la bandeja de salida (modo prueba)"
