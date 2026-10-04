from django.db import models

from taller.domain.appointment import Appointment


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
