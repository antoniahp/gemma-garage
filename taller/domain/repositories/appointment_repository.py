from abc import ABC, abstractmethod

from taller.domain.appointment import Appointment
from taller.domain.repositories.appointment_criteria import AppointmentCriteria


class AppointmentRepository(ABC):
    @abstractmethod
    def save(self, appointment: Appointment) -> None:
        raise NotImplementedError

    @abstractmethod
    def find_by_criteria(self, criteria: AppointmentCriteria) -> list[Appointment]:
        raise NotImplementedError

    @abstractmethod
    def find_or_fail_by_id(self, id: int) -> Appointment:
        raise NotImplementedError

    @abstractmethod
    def find_by_plate(self, normalized_plate: str, limit: int) -> list[Appointment]:
        """Citas de esa matrícula (sin espacios ni guiones), la más reciente primero."""
        raise NotImplementedError

    @abstractmethod
    def search(self, text: str, limit: int) -> list[Appointment]:
        """Busca por nota, matrícula, cliente, teléfono, vehículo o trabajo."""
        raise NotImplementedError

    @abstractmethod
    def update_parts(self, id: int, parts: list) -> None:
        raise NotImplementedError

    @abstractmethod
    def mark_ordered(self, id: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def record_order_error(self, id: int, message: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def mark_done(self, id: int) -> None:
        raise NotImplementedError
