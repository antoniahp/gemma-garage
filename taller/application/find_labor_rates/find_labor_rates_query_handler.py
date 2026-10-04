from taller.domain.known_services import KNOWN_SERVICES
from taller.domain.repositories.labor_rate_repository import LaborRateRepository

from taller.application.find_labor_rates.find_labor_rates_query import FindLaborRatesQuery


class FindLaborRatesQueryHandler:
    def __init__(self, labor_rate_repository: LaborRateRepository):
        self.labor_rate_repository = labor_rate_repository

    def handle(self, query: FindLaborRatesQuery) -> list[dict]:
        """Una fila por trabajo: los conocidos primero y después los que el taller haya añadido."""
        saved = {r.service: r.price for r in self.labor_rate_repository.find_all()}
        extra = sorted(set(saved) - set(KNOWN_SERVICES), key=str.lower)
        return [{"name": name, "price": saved.get(name)} for name in list(KNOWN_SERVICES) + extra]
