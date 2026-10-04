from taller.domain.exceptions.invoice_not_found_exception import InvoiceNotFoundException
from taller.domain.invoice import Invoice
from taller.domain.repositories.invoice_criteria import InvoiceCriteria
from taller.domain.repositories.invoice_repository import InvoiceRepository

from taller.application.find_invoice.find_invoice_query import FindInvoiceQuery


class FindInvoiceQueryHandler:
    def __init__(self, invoice_repository: InvoiceRepository):
        self.invoice_repository = invoice_repository

    def handle(self, query: FindInvoiceQuery) -> Invoice:
        """La factura de una cita. Lanza InvoiceNotFoundException si aún no tiene."""
        found = self.invoice_repository.find_by_criteria(InvoiceCriteria(appointment_id=query.appointment_id))
        if not found:
            raise InvoiceNotFoundException(query.appointment_id)
        return found[0]

    def find_or_none(self, query: FindInvoiceQuery) -> Invoice | None:
        found = self.invoice_repository.find_by_criteria(InvoiceCriteria(appointment_id=query.appointment_id))
        return found[0] if found else None
