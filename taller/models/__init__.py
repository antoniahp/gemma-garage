"""Django busca los modelos aquí; viven en taller/domain/."""

from taller.domain.appointment import Appointment
from taller.domain.client import Client
from taller.domain.invoice import Invoice
from taller.domain.labor_rate import LaborRate
from taller.domain.order import Order
from taller.domain.reminder import Reminder

from taller.domain.client import new_link_token  # noqa: F401  (lo usa la migración 0001)

__all__ = ["Client", "Appointment", "Order", "Reminder", "LaborRate", "Invoice"]
