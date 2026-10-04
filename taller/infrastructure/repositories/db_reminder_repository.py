from taller.domain.reminder import Reminder
from taller.domain.repositories.reminder_criteria import ReminderCriteria
from taller.domain.repositories.reminder_repository import ReminderRepository


class DbReminderRepository(ReminderRepository):
    def save(self, reminder: Reminder) -> None:
        reminder.save()

    def find_by_criteria(self, criteria: ReminderCriteria, limit: int | None = None) -> list[Reminder]:
        queryset = Reminder.objects.select_related("client")
        if criteria.appointment_id is not None:
            queryset = queryset.filter(appointment_id=criteria.appointment_id)
        if criteria.sent is not None:
            queryset = queryset.filter(sent=criteria.sent)
        if criteria.send_on_lte is not None:
            queryset = queryset.filter(send_on__lte=criteria.send_on_lte)
        return list(queryset[:limit] if limit else queryset)

    def mark_sent(self, id: int, detail: str) -> None:
        Reminder.objects.filter(pk=id).update(sent=True, detail=detail[:200])

    def delete_unsent_of_appointment(self, appointment_id: int) -> None:
        Reminder.objects.filter(appointment_id=appointment_id, sent=False).delete()
