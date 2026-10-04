from taller.domain.labor_rate_matching import match_labor_price
from taller.domain.repositories.labor_rate_repository import LaborRateRepository

from taller.application.find_labor_price.find_labor_price_query import FindLaborPriceQuery


class FindLaborPriceQueryHandler:
    def __init__(self, labor_rate_repository: LaborRateRepository):
        self.labor_rate_repository = labor_rate_repository

    def handle(self, query: FindLaborPriceQuery):
        """Precio de mano de obra de un trabajo, o None si no hay tarifa."""
        rates = {r.service: r.price for r in self.labor_rate_repository.find_all()}
        return match_labor_price(rates, query.service)
