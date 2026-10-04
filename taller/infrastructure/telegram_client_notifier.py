from django.conf import settings

from taller.domain.client_notifier import ClientNotifier
from taller.infrastructure import telegram_api


class TelegramClientNotifier(ClientNotifier):
    def notify_owner(self, text):
        if not settings.TELEGRAM_OWNER_CHAT_ID:
            return False, "falta TELEGRAM_OWNER_CHAT_ID"
        try:
            telegram_api.send(settings.TELEGRAM_OWNER_CHAT_ID, text)
        except telegram_api.TelegramError as exc:
            return False, str(exc)
        return True, "enviado al mecánico por Telegram"

    def notify_client(self, client, text):
        if client.telegram_linked:
            try:
                telegram_api.send(client.telegram_chat_id, text)
            except telegram_api.TelegramError as exc:
                return False, str(exc)
            return True, "enviado al cliente por Telegram"
        # El cliente aún no ha abierto el bot: se lo pasamos al mecánico para que le llame.
        phone = f" ({client.phone})" if client.phone else ""
        ok, detail = self.notify_owner(
            f"Este cliente no tiene Telegram vinculado. Avísale tú: {client.name}{phone}\n\n{text}"
        )
        return ok, "sin Telegram vinculado; " + detail
