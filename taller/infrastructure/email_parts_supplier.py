"""Pedido por correo (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SUPPLIER_EMAIL).

Bosch, Lozano y otros distribuidores no suelen tener una API pública estándar: lo habitual es
pedir por correo o por su portal. Para un portal concreto, crea otro adaptador de PartsSupplier
y devuélvelo en taller/container.py.
"""

import os
import smtplib
from email.message import EmailMessage

from taller.domain.parts_supplier import PartsSupplier
from taller.infrastructure.outbox import format_parts


class EmailPartsSupplier(PartsSupplier):
    name = "email"

    def send_order(self, order: dict) -> str:
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
