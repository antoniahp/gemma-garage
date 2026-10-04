from django.db import models

from taller.domain.appointment import Appointment


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
