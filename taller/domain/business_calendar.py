"""Calendario laboral: sumar meses y moverse entre días laborables."""

import calendar
from datetime import date, timedelta


def add_months(d, months):
    """Suma meses respetando fin de mes (29 feb -> 28 feb)."""
    index = d.month - 1 + months
    year, month = d.year + index // 12, index % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def previous_business_day(d):
    """Día laborable anterior (el lunes se pide el viernes)."""
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def next_business_day(d):
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d
