from abc import ABC, abstractmethod

from taller.domain.reminder import Reminder
from taller.domain.repositories.reminder_criteria import ReminderCriteria


class ReminderRepository(ABC):
    @abstractmethod
    def save(self, reminder: Reminder) -> None:
        raise NotImplementedError

    @abstractmethod
    def find_by_criteria(self, criteria: ReminderCriteria, limit: int | None = None) -> list[Reminder]:
        raise NotImplementedError

    @abstractmethod
    def mark_sent(self, id: int, detail: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete_unsent_of_appointment(self, appointment_id: int) -> None:
        raise NotImplementedError
