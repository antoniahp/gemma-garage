"""Limpieza de lo que devuelve un intérprete de notas (sobre todo si es un modelo de IA)."""

import re

GENERIC_SERVICES = {"mantenimiento", "reparación", "reparacion", "mantenimiento y reparación",
                    "mantenimiento y reparacion", "revisión", "revision"}


def clean_vehicle(text):
    text = " ".join(str(text or "").split())
    return "" if "desconocid" in text.lower() or text.lower() in ("n/a", "no indicado", "ninguno") else text


def clean_parts(parts):
    out, seen = [], set()
    for p in parts or []:
        if not isinstance(p, dict) or not p.get("name"):
            continue
        try:
            qty = float(p.get("qty", 1))
        except (TypeError, ValueError):
            qty = 1
        name = " ".join(str(p["name"]).split()).lower()
        spec = " ".join(str(p.get("spec", "")).split())
        if len(spec) > 14 or spec.lower() in name:  # una descripción, no una especificación
            spec = ""
        key = (name, spec.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "name": name,
                "spec": spec.upper() if re.fullmatch(r"\d{1,2}\s*w\s*-?\s*\d{2}", spec, re.I) else spec,
                "qty": int(qty) if qty == int(qty) else qty,
                "unit": str(p.get("unit", "ud")).strip() or "ud",
            }
        )
    return out
