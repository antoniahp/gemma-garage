import re
import secrets

from django.conf import settings
from django.db import models


def new_link_token():
    return secrets.token_urlsafe(8)


class Client(models.Model):
    name = models.CharField("nombre", max_length=120)
    phone = models.CharField("teléfono", max_length=30, blank=True)
    telegram_chat_id = models.BigIntegerField(
        "Telegram (chat)", null=True, blank=True, editable=False
    )
    link_token = models.CharField(
        max_length=32, unique=True, default=new_link_token, editable=False
    )

    class Meta:
        verbose_name = "cliente"
        verbose_name_plural = "clientes"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def telegram_linked(self):
        return self.telegram_chat_id is not None

    @property
    def phone_digits(self):
        """Teléfono listo para enlaces; a un móvil/fijo de 9 cifras le pone el 34 de España."""
        digits = re.sub(r"\D", "", self.phone or "")
        if digits.startswith("00"):
            digits = digits[2:]
        return "34" + digits if len(digits) == 9 else digits

    @property
    def tel_url(self):
        return f"tel:+{self.phone_digits}" if self.phone_digits else ""

    @property
    def whatsapp_url(self):
        return f"https://wa.me/{self.phone_digits}" if self.phone_digits else ""

    @property
    def telegram_link(self):
        bot = getattr(settings, "TELEGRAM_BOT_USERNAME", "")
        return f"https://t.me/{bot}?start={self.link_token}" if bot else ""
