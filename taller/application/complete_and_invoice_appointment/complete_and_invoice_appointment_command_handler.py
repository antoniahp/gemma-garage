from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from taller.application.find_labor_price.find_labor_price_query import FindLaborPriceQuery
from taller.application.find_labor_price.find_labor_price_query_handler import FindLaborPriceQueryHandler
from taller.domain.invoice import Invoice
from taller.domain.money import IVA, money
from taller.domain.repositories.appointment_repository import AppointmentRepository
from taller.domain.repositories.invoice_criteria import InvoiceCriteria
from taller.domain.repositories.invoice_repository import InvoiceRepository

from taller.application.complete_and_invoice_appointment.complete_and_invoice_appointment_command import CompleteAndInvoiceAppointmentCommand


class CompleteAndInvoiceAppointmentCommandHandler:
    def __init__(self, appointment_repository: AppointmentRepository, invoice_repository: InvoiceRepository,
                 find_labor_price: FindLaborPriceQueryHandler):
        self.appointment_repository = appointment_repository
        self.invoice_repository = invoice_repository
        self.find_labor_price = find_labor_price

    @transaction.atomic
    def handle(self, command: CompleteAndInvoiceAppointmentCommand) -> Invoice:
        """Marca la cita como hecha y genera la factura (una por cita).

        part_prices: precio unitario de cada recambio, en el orden de la cita (los recambios no
                     tienen precio guardado: dependen del distribuidor).
        labor:       mano de obra; si es None se usa la tarifa del trabajo.
        extras:      pares (concepto, importe) adicionales.
        """
        appointment = self.appointment_repository.find_or_fail_by_id(command.appointment_id)
        existing = self.invoice_repository.find_by_criteria(InvoiceCriteria(appointment_id=appointment.pk))
        if existing:
            return existing[0]

        part_prices = list(command.part_prices or [])
        lines = []
        for i, p in enumerate(appointment.parts):
            qty = Decimal(str(p["qty"]))
            price = Decimal(part_prices[i]) if i < len(part_prices) and part_prices[i] is not None else Decimal("0")
            lines.append({
                "concept": f"{p['name']} {p.get('spec', '')}".strip(),
                "qty": str(qty), "unit_price": str(money(price)), "amount": str(money(qty * price)),
            })
        labor = command.labor
        if labor is None:
            labor = self.find_labor_price.handle(FindLaborPriceQuery(service=appointment.service))
        if labor:
            lines.append({
                "concept": f"Mano de obra: {appointment.service}",
                "qty": "1", "unit_price": str(money(labor)), "amount": str(money(labor)),
            })
        for concept, amount in command.extras:
            lines.append({"concept": concept, "qty": "1", "unit_price": str(money(amount)),
                          "amount": str(money(amount))})
        subtotal = money(sum(Decimal(line["amount"]) for line in lines))
        iva = money(subtotal * IVA)
        today = timezone.localdate()
        count = self.invoice_repository.count_by_year(today.year) + 1
        invoice = Invoice(
            appointment=appointment, number=f"{today.year}-{count:04d}", created_at=today,
            lines=lines, subtotal=subtotal, iva=iva, total=subtotal + iva,
        )
        self.invoice_repository.save(invoice)
        self.appointment_repository.mark_done(appointment.pk)
        return invoice
