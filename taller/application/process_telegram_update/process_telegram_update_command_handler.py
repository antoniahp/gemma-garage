from taller.domain.repositories.client_criteria import ClientCriteria
from taller.domain.repositories.client_repository import ClientRepository

from taller.application.process_telegram_update.process_telegram_update_command import ProcessTelegramUpdateCommand


class ProcessTelegramUpdateCommandHandler:
    def __init__(self, client_repository: ClientRepository, reply):
        """reply(chat_id, texto): cómo se contesta por el bot (lo pone la infraestructura)."""
        self.client_repository = client_repository
        self.reply = reply

    def handle(self, command: ProcessTelegramUpdateCommand) -> str:
        """Procesa un mensaje recibido por el bot. Devuelve una descripción (para logs/tests)."""
        msg = command.update.get("message") or {}
        text = (msg.get("text") or "").strip()
        chat_id = (msg.get("chat") or {}).get("id")
        if not chat_id or not text:
            return "ignorado"

        if text.startswith("/id"):
            self.reply(chat_id, f"Tu id de chat es: {chat_id}")
            return "id"

        if text.startswith("/start"):
            parts = text.split(maxsplit=1)
            token = parts[1].strip() if len(parts) > 1 else ""
            found = self.client_repository.find_by_criteria(ClientCriteria(link_token=token)) if token else []
            if not found:
                self.reply(chat_id, "Hola. Para recibir avisos del taller, abre el enlace que te dio el taller.")
                return "sin_enlace"
            client = found[0]
            client.telegram_chat_id = chat_id
            self.client_repository.save(client)
            self.reply(chat_id, f"Hola {client.name}, listo: te avisaremos por aquí cuando toque revisar tu coche.")
            return f"vinculado:{client.pk}"

        return "ignorado"
