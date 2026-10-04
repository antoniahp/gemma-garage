"""Cliente mínimo de la API de bots de Telegram (solo librería estándar).

Flujo para avisar a un cliente:
  1. El mecánico le pasa el enlace del cliente (admin -> Clientes), p. ej.
     https://t.me/MiTallerBot?start=AbC123
  2. El cliente lo abre y pulsa "Iniciar". Un bot no puede escribir a nadie
     que no haya hablado antes con él: es una norma de Telegram.
  3. `python manage.py telegram_bot` recibe ese /start y guarda el chat del cliente.
"""

import json
import urllib.error
import urllib.request

from django.conf import settings

from .models import Client


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


def handle_update(update, reply=send):
    """Procesa un mensaje recibido por el bot. Devuelve una descripción (para logs/tests)."""
    msg = update.get("message") or {}
    text = (msg.get("text") or "").strip()
    chat_id = (msg.get("chat") or {}).get("id")
    if not chat_id or not text:
        return "ignorado"

    if text.startswith("/id"):
        reply(chat_id, f"Tu id de chat es: {chat_id}")
        return "id"

    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        token = parts[1].strip() if len(parts) > 1 else ""
        client = Client.objects.filter(link_token=token).first() if token else None
        if not client:
            reply(chat_id, "Hola. Para recibir avisos del taller, abre el enlace que te dio el taller.")
            return "sin_enlace"
        client.telegram_chat_id = chat_id
        client.save(update_fields=["telegram_chat_id"])
        reply(chat_id, f"Hola {client.name}, listo: te avisaremos por aquí cuando toque revisar tu coche.")
        return f"vinculado:{client.pk}"

    return "ignorado"
