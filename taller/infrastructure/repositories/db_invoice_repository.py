from taller.domain.invoice import Invoice
from taller.domain.repositories.invoice_criteria import InvoiceCriteria
from taller.domain.repositories.invoice_repository import InvoiceRepository


class DbInvoiceRepository(InvoiceRepository):
    def save(self, invoice: Invoice) -> None:
        invoice.save()

    def find_by_criteria(self, criteria: InvoiceCriteria) -> list[Invoice]:
        queryset = Invoice.objects.select_related("appointment__client")
        if criteria.appointment_id is not None:
            queryset = queryset.filter(appointment_id=criteria.appointment_id)
        return list(queryset)

    def count_by_year(self, year: int) -> int:
        return Invoice.objects.filter(created_at__year=year).count()
