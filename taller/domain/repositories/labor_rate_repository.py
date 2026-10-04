from abc import ABC, abstractmethod
from decimal import Decimal

from taller.domain.labor_rate import LaborRate


class LaborRateRepository(ABC):
    @abstractmethod
    def find_all(self) -> list[LaborRate]:
        raise NotImplementedError

    @abstractmethod
    def save_price(self, service: str, price: Decimal) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete_by_service(self, service: str) -> None:
        raise NotImplementedError
