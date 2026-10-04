from decimal import Decimal

from taller.domain.labor_rate import LaborRate
from taller.domain.repositories.labor_rate_repository import LaborRateRepository


class DbLaborRateRepository(LaborRateRepository):
    def find_all(self) -> list[LaborRate]:
        return list(LaborRate.objects.all())

    def save_price(self, service: str, price: Decimal) -> None:
        LaborRate.objects.update_or_create(service=service, defaults={"price": price})

    def delete_by_service(self, service: str) -> None:
        LaborRate.objects.filter(service=service).delete()
