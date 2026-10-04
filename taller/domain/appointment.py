from django.db import models
from django.utils import formats, timezone

from taller.domain.business_calendar import previous_business_day
from taller.domain.client import Client


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
