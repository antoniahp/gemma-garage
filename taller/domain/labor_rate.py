from django.db import models


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
