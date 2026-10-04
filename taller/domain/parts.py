"""Recambios: cantidades y lista de compra (lógica pura, sin base de datos)."""


def parse_qty(text):
    """'4', '1,5' -> número; devuelve None si no es válido o no es positivo."""
    try:
        qty = float(str(text).replace(",", ".").strip())
    except ValueError:
        return None
    if qty <= 0:
        return None
    return int(qty) if qty == int(qty) else qty


def describe_parts(parts):
    return ", ".join(f"{p['qty']} {p['name']} {p.get('spec', '')}".strip() for p in parts)


def shopping_list(appointments):
    """Suma los recambios iguales de varias citas: lista de filas {name, spec, unit, qty, cars}."""
    totals = {}
    for appt in appointments:
        car = " ".join(x for x in (appt.vehicle, appt.plate) if x) or appt.client.name
        for p in appt.parts:
            key = (p["name"].lower(), p.get("spec", "").upper(), p.get("unit", "ud"))
            row = totals.setdefault(key, {"name": p["name"], "spec": p.get("spec", ""),
                                          "unit": p.get("unit", "ud"), "qty": 0, "cars": []})
            row["qty"] += p["qty"]
            if car not in row["cars"]:
                row["cars"].append(car)
    rows = sorted(totals.values(), key=lambda r: r["name"].lower())
    for r in rows:
        r["qty"] = round(r["qty"], 2)
        if r["qty"] == int(r["qty"]):
            r["qty"] = int(r["qty"])
    return rows
