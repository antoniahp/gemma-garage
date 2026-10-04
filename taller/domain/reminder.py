from django.db import models

from taller.domain.appointment import Appointment
from taller.domain.client import Client


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
