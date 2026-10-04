from dataclasses import dataclass


@dataclass(frozen=True)
class ScheduleReminderCommand:
    appointment_id: int
