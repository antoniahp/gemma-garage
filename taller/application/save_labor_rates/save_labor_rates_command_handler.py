from taller.domain.repositories.labor_rate_repository import LaborRateRepository

from taller.application.save_labor_rates.save_labor_rates_command import SaveLaborRatesCommand


class SaveLaborRatesCommandHandler:
    def __init__(self, labor_rate_repository: LaborRateRepository):
        self.labor_rate_repository = labor_rate_repository

    def handle(self, command: SaveLaborRatesCommand) -> None:
        """entries: pares (trabajo, precio). Un precio None borra la tarifa de ese trabajo."""
        for service, price in command.entries:
            if price is None:
                self.labor_rate_repository.delete_by_service(service)
            else:
                self.labor_rate_repository.save_price(service, price)
