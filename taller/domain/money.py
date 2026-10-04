"""Dinero: IVA y redondeo."""

from decimal import ROUND_HALF_UP, Decimal

IVA = Decimal("0.21")


def money(x):
    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
