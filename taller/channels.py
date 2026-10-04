"""Canales de salida: pedido al proveedor y avisos al cliente.

Todo es intercambiable. Sin configuración, nada sale al exterior: los pedidos y
avisos se guardan en la bandeja de salida local (outbox/) para poder probar.

Pedido al proveedor (TALLER_SUPPLIER):
  - "outbox"  guarda el pedido en outbox/pedidos.jsonl (por defecto)
  - "email"   lo envía por correo (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SUPPLIER_EMAIL)
Bosch, Lozano y otros distribuidores no suelen tener una API pública estándar:
lo habitual es pedir por correo o por su portal. Para un portal concreto, crea otra
clase con send_order() y devuélvela en get_supplier().

Avisos al cliente: Telegram (gratis) si hay TELEGRAM_BOT_TOKEN; si no, outbox/avisos.jsonl.
"""

import json
import os
import smtplib
from datetime import datetime
from email.message import EmailMessage

from django.conf import settings

from . import telegram


def _append(filename, record):
    os.makedirs(settings.TALLER_OUTBOX, exist_ok=True)
    record = {"at": datetime.now().isoformat(timespec="seconds"), **record}
    with open(os.path.join(settings.TALLER_OUTBOX, filename), "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def format_parts(parts):
    lines = []
    for p in parts:
        spec = f" {p['spec']}" if p.get("spec") else ""
        lines.append(f"- {p['qty']} {p.get('unit', 'ud')} de {p['name']}{spec}")
    return "\n".join(lines)


# ---------- Proveedores ----------


class OutboxSupplier:
    name = "outbox"

    def send_order(self, order):
        _append("pedidos.jsonl", order)
        return "guardado en la bandeja de salida (modo prueba)"


class EmailSupplier:
    name = "email"

    def send_order(self, order):
        msg = EmailMessage()
        msg["Subject"] = f"Pedido de taller para {order['deliver_on']}"
        msg["From"] = os.environ.get("SMTP_USER", "taller@localhost")
        msg["To"] = os.environ["SUPPLIER_EMAIL"]
        msg.set_content(
            f"Buenos días,\n\nNecesitamos para el {order['deliver_on']} "
            f"({order['vehicle'] or 'vehículo'}, {order['service']}):\n\n"
            f"{format_parts(order['parts'])}\n\nGracias."
        )
        with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "587"))) as s:
            s.starttls()
            if os.environ.get("SMTP_USER"):
                s.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASS", ""))
            s.send_message(msg)
        return f"enviado por correo a {os.environ['SUPPLIER_EMAIL']}"


def get_supplier():
    return EmailSupplier() if settings.TALLER_SUPPLIER == "email" else OutboxSupplier()


# ---------- Avisos ----------


class Notifier:
    """Avisa a clientes y al mecánico. Devuelve (ok, detalle) y nunca lanza por un fallo de red."""

    def notify_owner(self, text):
        if not telegram.configured():
            _append("avisos.jsonl", {"to": "mecánico", "text": text})
            return True, "guardado en la bandeja de salida (modo prueba)"
        if not settings.TELEGRAM_OWNER_CHAT_ID:
            return False, "falta TELEGRAM_OWNER_CHAT_ID"
        try:
            telegram.send(settings.TELEGRAM_OWNER_CHAT_ID, text)
        except telegram.TelegramError as exc:
            return False, str(exc)
        return True, "enviado al mecánico por Telegram"

    def notify_client(self, client, text):
        if not telegram.configured():
            _append(
                "avisos.jsonl",
                {"to": client.name, "phone": client.phone, "linked": client.telegram_linked,
                 "text": text},
            )
            return True, "guardado en la bandeja de salida (modo prueba)"
        if client.telegram_linked:
            try:
                telegram.send(client.telegram_chat_id, text)
            except telegram.TelegramError as exc:
                return False, str(exc)
            return True, "enviado al cliente por Telegram"
        # El cliente aún no ha abierto el bot: se lo pasamos al mecánico para que le llame.
        phone = f" ({client.phone})" if client.phone else ""
        ok, detail = self.notify_owner(
            f"Este cliente no tiene Telegram vinculado. Avísale tú: {client.name}{phone}\n\n{text}"
        )
        return ok, "sin Telegram vinculado; " + detail


def get_notifier():
    return Notifier()
