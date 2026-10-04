"""Convierte la nota libre de la agenda en una cita estructurada.

Ejemplo: "cambio aceite motor opel aceite 5w30"
  -> servicio="cambio de aceite", vehiculo="Opel",
     recambios=[aceite 5W30 (4 L), filtro de aceite]

Primero intenta un modelo open-weight local (Gemma vía Ollama).
Si Ollama no está en marcha, usa reglas. El taller nunca se queda parado.
"""

import json
import os
import re
import socket
import urllib.error
import urllib.request

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("TALLER_MODEL", "gemma3")
OLLAMA_TIMEOUT = int(os.environ.get("TALLER_TIMEOUT", "60"))  # la 1.ª vez Ollama carga el modelo

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

PROMPT = """Eres el asistente de un taller mecánico en España. Lees la nota que el mecánico escribió en su \
agenda (puede tener faltas de ortografía) y la conviertes en JSON.
Responde SOLO con un JSON con esta forma:
{{"service": "...", "vehicle": "...", "repeat_months": 0,
  "parts": [{{"name": "...", "spec": "...", "qty": 1, "unit": "ud"}}]}}

Reglas:
- service: el trabajo en minúsculas y en pocas palabras, como lo diría un mecánico. Ejemplos: \
"cambio de aceite y filtros", "ITV", "cambio de pastillas de freno". Si hay varios trabajos, \
júntalos con " y ". Nunca uses palabras genéricas como "mantenimiento" o "reparación".
- vehicle: marca y modelo SOLO si aparecen en la nota o en "Vehículo". Si no, "" (vacío). \
Nunca escribas "desconocido".
- repeat_months: 12 para la ITV y el cambio de aceite; 0 en el resto.
- parts: piezas físicas que hay que comprar al proveedor, una línea por pieza. La ITV no lleva piezas. \
No inventes piezas que no se mencionan (salvo el filtro de aceite en un cambio de aceite).
  - name: en minúsculas, singular, corto y genérico: "aceite motor", "filtro de aceite", \
"filtro de aire", "filtro de combustible", "filtro de habitáculo", "pastillas de freno", \
"neumático", "batería", "escobillas limpiaparabrisas", "bombilla de freno".
  - "habitáculo" o "polen" es el filtro del aire del interior; "gasolina", "gasoil" o "diésel" es el \
filtro de combustible; "limpia parabrisas" son las escobillas limpiaparabrisas.
  - spec: solo un dato corto, como la viscosidad ("10W30") o "delanteras". Si no hay, "". \
Nunca pongas descripciones largas. Si la nota no dice la viscosidad del aceite, deja spec vacío.
  - qty y unit: el aceite motor va en litros ("L", 4 si no dice otra cantidad); el resto "ud" y 1.

Ejemplo:
Nota: cambio aceite motor opel corsa aceite 5w30
{{"service": "cambio de aceite", "vehicle": "Opel Corsa", "repeat_months": 12, "parts": [\
{{"name": "aceite motor", "spec": "5W30", "qty": 4, "unit": "L"}}, \
{{"name": "filtro de aceite", "spec": "", "qty": 1, "unit": "ud"}}]}}

Ejemplo:
Nota: pastillas delanteras y filtro de polen seat leon
{{"service": "cambio de pastillas de freno y filtro", "vehicle": "Seat Leon", "repeat_months": 0, "parts": [\
{{"name": "pastillas de freno", "spec": "delanteras", "qty": 1, "unit": "juego"}}, \
{{"name": "filtro de habitáculo", "spec": "", "qty": 1, "unit": "ud"}}]}}

Vehículo: {vehicle}
Nota: {note}"""


_CACHE = {}  # (modelo, nota, coche) -> respuesta; la vista previa y el guardado no repiten el trabajo


def _ask_ollama(note, vehicle="", timeout=None):
    key = (OLLAMA_MODEL, note.strip(), vehicle.strip())
    if key in _CACHE:
        return json.loads(json.dumps(_CACHE[key]))
    result = _ask_ollama_uncached(note, vehicle, timeout)
    if len(_CACHE) > 200:
        _CACHE.clear()
    _CACHE[key] = result
    return json.loads(json.dumps(result))


def _ask_ollama_uncached(note, vehicle="", timeout=None):
    timeout = timeout or OLLAMA_TIMEOUT
    body = json.dumps(
        {
            "model": OLLAMA_MODEL,
            "prompt": PROMPT.format(note=note, vehicle=vehicle or "(no indicado)"),
            "stream": False,
            "format": "json",
            "options": {"temperature": 0, "num_predict": 400},
            "keep_alive": os.environ.get("TALLER_KEEP_ALIVE", "30m"),
        }
    ).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    return json.loads(data["response"])


GENERIC_SERVICES = {"mantenimiento", "reparación", "reparacion", "mantenimiento y reparación",
                    "mantenimiento y reparacion", "revisión", "revision"}


def _clean_vehicle(text):
    text = " ".join(str(text or "").split())
    return "" if "desconocid" in text.lower() or text.lower() in ("n/a", "no indicado", "ninguno") else text


def _clean_parts(parts):
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
    text = note.lower()
    service, months, parts = "", 0, []
    # la clave más larga primero ("cambio aceite" antes que "aceite")
    for key in sorted(SERVICES, key=len, reverse=True):
        if key in text:
            service, months, default_parts = SERVICES[key]
            parts = [dict(p) for p in default_parts]
            break

    vehicle = _clean_vehicle(vehicle)
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

    return {
        "service": service or note.strip(),
        "vehicle": vehicle,
        "repeat_months": months,
        "parts": parts,
        "engine": "reglas",
    }


def explain_error(exc):
    """Por qué no se pudo usar Gemma, en lenguaje llano."""
    if isinstance(exc, urllib.error.HTTPError):
        try:
            detail = json.loads(exc.read()).get("error", "")
        except Exception:
            detail = ""
        if exc.code == 404 or "not found" in detail:
            return f"el modelo {OLLAMA_MODEL} no está descargado: ejecuta «ollama pull {OLLAMA_MODEL}»"
        return f"Ollama devolvió un error ({exc.code}) {detail}".strip()
    reason = getattr(exc, "reason", exc)
    if isinstance(exc, (socket.timeout, TimeoutError)) or isinstance(reason, (socket.timeout, TimeoutError)):
        return (f"Ollama tardó más de {OLLAMA_TIMEOUT} s (la primera vez carga el modelo): "
                "vuelve a intentarlo")
    if isinstance(exc, urllib.error.URLError):
        return f"no hay conexión con Ollama en {OLLAMA_URL}: arráncalo con «brew services start ollama»"
    if isinstance(exc, (ValueError, KeyError)):
        return "Gemma no devolvió una respuesta válida"
    return f"{type(exc).__name__}: {exc}"


def parse_note(note, use_llm=True, vehicle=""):
    """Devuelve dict con service, vehicle, repeat_months, parts, engine (y llm_error si Gemma falló).

    vehicle: marca y modelo escritos en el formulario; si se da, manda sobre lo que adivine la IA.
    """
    error = ""
    vehicle = _clean_vehicle(vehicle)
    if use_llm and os.environ.get("TALLER_NO_LLM") != "1":
        try:
            data = _ask_ollama(note, vehicle=vehicle)
            service = " ".join(str(data.get("service", "")).split())
            if service.lower() in GENERIC_SERVICES:
                service = ""
            result = {
                "service": service or parse_with_rules(note)["service"],
                "vehicle": vehicle or _clean_vehicle(data.get("vehicle")),
                "repeat_months": int(data.get("repeat_months", 0) or 0),
                "parts": _clean_parts(data.get("parts")),
                "engine": f"ollama:{OLLAMA_MODEL}",
            }
            if result["service"]:
                return result
        except Exception as exc:  # Ollama apagado o respuesta inválida -> reglas
            error = explain_error(exc)
    elif use_llm:
        error = "la IA está desactivada (TALLER_NO_LLM=1)"
    result = parse_with_rules(note, vehicle=vehicle)
    result["llm_error"] = error
    return result
