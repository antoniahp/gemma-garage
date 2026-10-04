from taller.domain.invoice import Invoice
from taller.domain.repositories.invoice_criteria import InvoiceCriteria
from taller.domain.repositories.invoice_repository import InvoiceRepository

from taller.application.find_invoices.find_invoices_query import FindInvoicesQuery


class FindInvoicesQueryHandler:
    def __init__(self, invoice_repository: InvoiceRepository):
        self.invoice_repository = invoice_repository

    def handle(self, query: FindInvoicesQuery) -> list[Invoice]:
        return self.invoice_repository.find_by_criteria(InvoiceCriteria())
