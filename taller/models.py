import re
import secrets
from datetime import date

from django.conf import settings
from django.db import models
from django.utils import formats, timezone

from .parser import parse_note


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


class Appointment(models.Model):
    STATUS = [("pendiente", "Pendiente"), ("hecha", "Hecha")]

    client = models.ForeignKey(
        Client, on_delete=models.PROTECT, verbose_name="cliente", related_name="appointments"
    )
    date = models.DateField("fecha")
    plate = models.CharField("matrícula", max_length=15, blank=True)
    note = models.TextField(
        "qué hay que hacer",
        help_text='Escríbelo como en papel. Ej.: "cambio aceite motor opel aceite 5w30"',
    )
    service = models.CharField("servicio", max_length=120, blank=True)
    vehicle = models.CharField("vehículo", max_length=60, blank=True)
    parts = models.JSONField("recambios", default=list, blank=True)
    repeat_months = models.PositiveIntegerField(
        "se repite cada (meses)", default=0, help_text="0 = no se repite"
    )
    status = models.CharField(max_length=10, choices=STATUS, default="pendiente")
    ordered = models.BooleanField("recambios pedidos", default=False)
    order_error = models.CharField("último error del pedido", max_length=200, blank=True)

    class Meta:
        verbose_name = "cita"
        verbose_name_plural = "citas"
        ordering = ["date", "id"]

    def __str__(self):
        return f"{self.date} · {self.service or self.note[:30]}"

    @property
    def order_date(self):
        """Día laborable en que se piden los recambios."""
        from .services import previous_business_day

        return previous_business_day(self.date)

    @property
    def order_state(self):
        if self.status == "hecha":
            return "hecha"
        if not self.parts:
            return "sin_recambios"
        if self.ordered:
            return "pedido"
        if self.order_error:
            return "fallo"
        return "pedir_hoy" if self.order_date <= timezone.localdate() else "por_pedir"

    @property
    def order_label(self):
        state = self.order_state
        if state == "por_pedir":
            return f"Se pide el {formats.date_format(self.order_date, 'l j')}"
        return {
            "hecha": "Hecha",
            "sin_recambios": "Sin recambios",
            "pedido": "Recambios pedidos",
            "pedir_hoy": "Toca pedir hoy",
            "fallo": "Falló el pedido",
        }[state]

    def interpret_note(self, use_llm=True):
        """Rellena servicio, vehículo, recambios y repetición a partir de la nota."""
        parsed = parse_note(self.note, use_llm=use_llm, vehicle=self.vehicle)
        self.service = parsed["service"]
        self.vehicle = parsed["vehicle"]
        self.parts = parsed["parts"]
        self.repeat_months = parsed["repeat_months"]
        return parsed

    def save(self, *args, **kwargs):
        creating = self._state.adding
        if not self.service and self.note:
            self.interpret_note()
        super().save(*args, **kwargs)
        if creating and self.repeat_months:
            from .services import schedule_reminder

            schedule_reminder(self)


class Order(models.Model):
    appointment = models.ForeignKey(
        Appointment, on_delete=models.CASCADE, verbose_name="cita", related_name="orders"
    )
    supplier = models.CharField("proveedor/canal", max_length=30)
    parts = models.JSONField("recambios")
    created_at = models.DateTimeField("enviado", auto_now_add=True)
    detail = models.CharField("detalle", max_length=200, blank=True)

    class Meta:
        verbose_name = "pedido"
        verbose_name_plural = "pedidos"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Pedido cita {self.appointment_id}"


class Reminder(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, verbose_name="cliente")
    appointment = models.ForeignKey(
        Appointment, on_delete=models.CASCADE, verbose_name="cita origen"
    )
    send_on = models.DateField("enviar el")
    message = models.TextField("mensaje")
    sent = models.BooleanField("enviado", default=False)
    detail = models.CharField("detalle", max_length=200, blank=True)

    class Meta:
        verbose_name = "aviso"
        verbose_name_plural = "avisos"
        ordering = ["send_on"]

    def __str__(self):
        return f"Aviso a {self.client} el {self.send_on}"


class LaborRate(models.Model):
    service = models.CharField(
        "trabajo", max_length=120, unique=True,
        help_text='Como lo entiende el programa. Ej.: "cambio de aceite"',
    )
    price = models.DecimalField("mano de obra (sin IVA)", max_digits=8, decimal_places=2)

    class Meta:
        verbose_name = "tarifa de mano de obra"
        verbose_name_plural = "tarifas de mano de obra"
        ordering = ["service"]

    def __str__(self):
        return f"{self.service}: {self.price} €"


class Invoice(models.Model):
    appointment = models.OneToOneField(
        Appointment, on_delete=models.PROTECT, verbose_name="cita", related_name="invoice"
    )
    number = models.CharField("número", max_length=20, unique=True)
    created_at = models.DateField("fecha")
    lines = models.JSONField("líneas")
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    iva = models.DecimalField("IVA", max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "factura"
        verbose_name_plural = "facturas"
        ordering = ["-number"]

    def __str__(self):
        return f"Factura {self.number}"
