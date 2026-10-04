from django.db.models import Q

from taller.domain.appointment import Appointment
from taller.domain.exceptions.appointment_not_found_exception import AppointmentNotFoundException
from taller.domain.plate import normalize_plate
from taller.domain.repositories.appointment_criteria import AppointmentCriteria
from taller.domain.repositories.appointment_repository import AppointmentRepository


class DbAppointmentRepository(AppointmentRepository):
    def save(self, appointment: Appointment) -> None:
        appointment.save()

    def find_by_criteria(self, criteria: AppointmentCriteria) -> list[Appointment]:
        queryset = Appointment.objects.select_related("client")
        if criteria.id is not None:
            queryset = queryset.filter(id=criteria.id)
        if criteria.ids is not None:
            queryset = queryset.filter(id__in=criteria.ids)
        if criteria.date is not None:
            queryset = queryset.filter(date=criteria.date)
        if criteria.date_gte is not None:
            queryset = queryset.filter(date__gte=criteria.date_gte)
        if criteria.date_lte is not None:
            queryset = queryset.filter(date__lte=criteria.date_lte)
        if criteria.date_lt is not None:
            queryset = queryset.filter(date__lt=criteria.date_lt)
        if criteria.status is not None:
            queryset = queryset.filter(status=criteria.status)
        if criteria.ordered is not None:
            queryset = queryset.filter(ordered=criteria.ordered)
        if criteria.with_order_error is True:
            queryset = queryset.exclude(order_error="")
        elif criteria.with_order_error is False:
            queryset = queryset.filter(order_error="")
        return list(queryset)

    def find_or_fail_by_id(self, id: int) -> Appointment:
        try:
            return Appointment.objects.select_related("client").get(id=id)
        except Appointment.DoesNotExist:
            raise AppointmentNotFoundException(id)

    def find_by_plate(self, normalized_plate: str, limit: int) -> list[Appointment]:
        rows = Appointment.objects.exclude(plate="").select_related("client").order_by("-date")
        return [a for a in rows if normalize_plate(a.plate) == normalized_plate][:limit]

    def search(self, text: str, limit: int) -> list[Appointment]:
        cond = (Q(note__icontains=text) | Q(plate__icontains=text) | Q(client__name__icontains=text)
                | Q(vehicle__icontains=text) | Q(service__icontains=text)
                | Q(client__phone__icontains=text))
        found = list(Appointment.objects.filter(cond).select_related("client").order_by("-date")[:limit])
        norm = normalize_plate(text)
        if norm and len(norm) >= 4:  # "1234 abc" también encuentra "1234ABC"
            extra = [a for a in Appointment.objects.exclude(plate="").select_related("client")
                     if norm in normalize_plate(a.plate) and a not in found]
            found = sorted(found + extra, key=lambda a: a.date, reverse=True)[:limit]
        return found

    def update_parts(self, id: int, parts: list) -> None:
        Appointment.objects.filter(pk=id).update(parts=parts)

    def mark_ordered(self, id: int) -> None:
        Appointment.objects.filter(pk=id).update(ordered=True, order_error="")

    def record_order_error(self, id: int, message: str) -> None:
        Appointment.objects.filter(pk=id).update(order_error=message[:200] or "error")

    def mark_done(self, id: int) -> None:
        Appointment.objects.filter(pk=id).update(status="hecha")
