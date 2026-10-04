from abc import ABC, abstractmethod

from taller.domain.invoice import Invoice
from taller.domain.repositories.invoice_criteria import InvoiceCriteria


class InvoiceRepository(ABC):
    @abstractmethod
    def save(self, invoice: Invoice) -> None:
        raise NotImplementedError

    @abstractmethod
    def find_by_criteria(self, criteria: InvoiceCriteria) -> list[Invoice]:
        raise NotImplementedError

    @abstractmethod
    def count_by_year(self, year: int) -> int:
        raise NotImplementedError
