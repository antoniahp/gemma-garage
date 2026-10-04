"""Cliente mínimo de la API de bots de Telegram (solo librería estándar).

Flujo para avisar a un cliente:
  1. El mecánico le pasa el enlace del cliente (pantalla Clientes), p. ej.
     https://t.me/MiTallerBot?start=AbC123
  2. El cliente lo abre y pulsa "Iniciar". Un bot no puede escribir a nadie
     que no haya hablado antes con él: es una norma de Telegram.
  3. `python manage.py telegram_bot` recibe ese /start y guarda el chat del cliente.
"""

import json
import urllib.error
import urllib.request

from django.conf import settings


class TelegramError(Exception):
    pass


def configured():
    return bool(settings.TELEGRAM_BOT_TOKEN)


def api(method, payload=None, timeout=40):
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload or {}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        # El token va en la URL: no lo mostramos en el error.
        raise TelegramError(f"Telegram respondió {exc.code} a {method}") from None
    except urllib.error.URLError as exc:
        raise TelegramError(f"No se pudo contactar con Telegram: {exc.reason}") from None
    if not data.get("ok"):
        raise TelegramError(data.get("description", "error desconocido"))
    return data["result"]


def send(chat_id, text):
    api("sendMessage", {"chat_id": chat_id, "text": text})
