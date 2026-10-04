"""Elige la tarifa de mano de obra que corresponde a un trabajo."""

import unicodedata


def normalize(text):
    text = unicodedata.normalize("NFD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).lower().strip()


def match_labor_price(rates, service):
    """rates: {nombre_del_trabajo: precio}. Devuelve el precio o None si no hay tarifa.

    Primero busca el nombre exacto y luego el más largo que esté contenido en el trabajo
    ("cambio de aceite y filtro" -> "cambio de aceite").
    """
    by_name = {normalize(name): price for name, price in rates.items()}
    key = normalize(service)
    if key in by_name:
        return by_name[key]
    for name in sorted(by_name, key=len, reverse=True):
        if name and (name in key or key in name):
            return by_name[name]
    return None
