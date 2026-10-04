from taller.domain.client_notifier import ClientNotifier
from taller.infrastructure import outbox


class OutboxClientNotifier(ClientNotifier):
    """Modo prueba (sin bot de Telegram): los avisos se guardan en outbox/avisos.jsonl."""

    def notify_owner(self, text):
        outbox.append("avisos.jsonl", {"to": "mecánico", "text": text})
        return True, "guardado en la bandeja de salida (modo prueba)"

    def notify_client(self, client, text):
        outbox.append(
            "avisos.jsonl",
            {"to": client.name, "phone": client.phone, "linked": client.telegram_linked, "text": text},
        )
        return True, "guardado en la bandeja de salida (modo prueba)"
