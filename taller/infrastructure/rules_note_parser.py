"""Intérprete de notas con reglas simples: no necesita IA y cubre los trabajos habituales."""

import re

from taller.domain.note_cleaning import clean_vehicle
from taller.domain.note_parser import NoteParser
from taller.domain.parsed_note import ParsedNote

BRANDS = [
    "opel",
    "seat",
    "renault",
    "peugeot",
    "citroen",
    "citroën",
    "ford",
    "volkswagen",
    "vw",
    "audi",
    "bmw",
    "mercedes",
    "toyota",
    "nissan",
    "fiat",
    "dacia",
    "kia",
    "hyundai",
    "skoda",
    "mazda",
    "honda",
    "volvo",
    "mini",
    "suzuki",
]

# palabra clave -> (nombre del servicio, meses hasta el próximo, recambios por defecto)
SERVICES = {
    "itv": ("ITV", 12, []),
    "cambio aceite": (
        "cambio de aceite",
        12,
        [
            {"name": "aceite motor", "spec": "", "qty": 4, "unit": "L"},
            {"name": "filtro de aceite", "spec": "", "qty": 1, "unit": "ud"},
        ],
    ),
    "aceite": (
        "cambio de aceite",
        12,
        [
            {"name": "aceite motor", "spec": "", "qty": 4, "unit": "L"},
            {"name": "filtro de aceite", "spec": "", "qty": 1, "unit": "ud"},
        ],
    ),
    "pastillas": (
        "cambio de pastillas de freno",
        24,
        [
            {"name": "pastillas de freno", "spec": "", "qty": 1, "unit": "juego"},
        ],
    ),
    "frenos": (
        "revisión de frenos",
        12,
        [
            {"name": "pastillas de freno", "spec": "", "qty": 1, "unit": "juego"},
        ],
    ),
    "neumaticos": (
        "cambio de neumáticos",
        0,
        [
            {"name": "neumático", "spec": "", "qty": 4, "unit": "ud"},
        ],
    ),
    "neumáticos": (
        "cambio de neumáticos",
        0,
        [
            {"name": "neumático", "spec": "", "qty": 4, "unit": "ud"},
        ],
    ),
    "filtro": (
        "cambio de filtros",
        12,
        [
            {"name": "filtro de aire", "spec": "", "qty": 1, "unit": "ud"},
            {"name": "filtro de habitáculo", "spec": "", "qty": 1, "unit": "ud"},
        ],
    ),
    "correa": (
        "cambio de correa de distribución",
        0,
        [
            {"name": "kit de distribución", "spec": "", "qty": 1, "unit": "kit"},
        ],
    ),
    "bateria": (
        "cambio de batería",
        0,
        [
            {"name": "batería", "spec": "", "qty": 1, "unit": "ud"},
        ],
    ),
    "batería": (
        "cambio de batería",
        0,
        [
            {"name": "batería", "spec": "", "qty": 1, "unit": "ud"},
        ],
    ),
}

FILTER_KINDS = [
    (r"\baire\b", "filtro de aire"),
    (r"\b(?:gasolina|combustible|gasoil|diesel|diésel)\b", "filtro de combustible"),
    (r"\b(?:habit[aá]culo|polen)\b", "filtro de habitáculo"),
    (r"\baceite\b", "filtro de aceite"),
]


def _apply_filters(text, service, parts):
    """"filtros de aire aceite y gasolina" -> un recambio por cada filtro nombrado."""
    pos = text.find("filtro")
    if pos < 0:
        return service, parts
    kinds = [name for rx, name in FILTER_KINDS if re.search(rx, text[pos:])]
    if not kinds:
        return service, parts
    if service == "cambio de filtros":
        parts = []  # los filtros de la nota sustituyen a los de por defecto
    have = {p["name"] for p in parts}
    for name in kinds:
        if name not in have:
            parts.append({"name": name, "spec": "", "qty": 1, "unit": "ud"})
    if service == "cambio de aceite" and any(k != "filtro de aceite" for k in kinds):
        service = "cambio de aceite y filtros"
    return service, parts


def parse_with_rules(note, vehicle=""):
    """Interpreta la nota con reglas simples (sin IA)."""
    text = note.lower()
    service, months, parts = "", 0, []
    # la clave más larga primero ("cambio aceite" antes que "aceite")
    for key in sorted(SERVICES, key=len, reverse=True):
        if key in text:
            service, months, default_parts = SERVICES[key]
            parts = [dict(p) for p in default_parts]
            break

    vehicle = clean_vehicle(vehicle)
    for brand in BRANDS if not vehicle else []:
        if re.search(rf"\b{re.escape(brand)}\b", text):
            vehicle = brand.upper() if brand in ("bmw", "vw") else brand.capitalize()
            break

    service, parts = _apply_filters(text, service, parts)

    # viscosidad del aceite escrita en la nota (5w30, 10w-40, 0w20...)
    visc = re.search(r"\b(\d{1,2})\s*w\s*-?\s*(\d{2})\b", text)
    if visc:
        spec = f"{visc.group(1)}W{visc.group(2)}"
        for p in parts:
            if p["name"] == "aceite motor":
                p["spec"] = spec
    # litros escritos en la nota ("5l", "5 litros")
    liters = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(?:l|lt|lts|litros)\b", text)
    if liters:
        qty = float(liters.group(1).replace(",", "."))
        for p in parts:
            if p["name"] == "aceite motor":
                p["qty"] = int(qty) if qty == int(qty) else qty

    return ParsedNote(
        service=service or note.strip(), vehicle=vehicle, repeat_months=months, parts=parts,
        engine="reglas",
    )


class RulesNoteParser(NoteParser):
    def parse(self, note: str, vehicle: str = "") -> ParsedNote:
        return parse_with_rules(note, vehicle=vehicle)
