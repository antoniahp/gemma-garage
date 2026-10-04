import time

from django.core.management.base import BaseCommand, CommandError

from taller import container
from taller.application.process_telegram_update.process_telegram_update_command import (
    ProcessTelegramUpdateCommand,
)
from taller.infrastructure import telegram_api


class Command(BaseCommand):
    help = "Escucha el bot de Telegram para vincular a los clientes (déjalo en marcha)."

    def handle(self, *args, **options):
        if not telegram_api.configured():
            raise CommandError("Falta TELEGRAM_BOT_TOKEN (créalo con @BotFather en Telegram).")
        self.stdout.write("Bot en marcha. Ctrl+C para salir.")
        offset = None
        while True:
            try:
                payload = {"timeout": 30, "allowed_updates": ["message"]}
                if offset is not None:
                    payload["offset"] = offset
                for update in telegram_api.api("getUpdates", payload, timeout=40):
                    offset = update["update_id"] + 1
                    result = container.process_telegram_update_handler().handle(
                        ProcessTelegramUpdateCommand(update=update))
                    self.stdout.write(f"update {update['update_id']}: {result}")
            except telegram_api.TelegramError as exc:
                self.stderr.write(f"{exc}; reintento en 10 s")
                time.sleep(10)
            except KeyboardInterrupt:
                break
