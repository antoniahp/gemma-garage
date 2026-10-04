"""Intérprete de notas con un modelo open-weight local (Gemma vía Ollama).

Si Ollama está apagado, no tiene el modelo o devuelve algo inválido, lanza
NoteParserUnavailableException con una explicación en lenguaje llano; quien lo use decide el respaldo.
"""

import json
import os
import socket
import urllib.error
import urllib.request

from taller.domain.note_cleaning import GENERIC_SERVICES, clean_parts, clean_vehicle
from taller.domain.note_parser import NoteParser, NoteParserUnavailableException
from taller.domain.parsed_note import ParsedNote
from taller.infrastructure.rules_note_parser import parse_with_rules

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("TALLER_MODEL", "gemma3")
OLLAMA_TIMEOUT = int(os.environ.get("TALLER_TIMEOUT", "60"))  # la 1.ª vez Ollama carga el modelo

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


class OllamaNoteParser(NoteParser):
    def parse(self, note: str, vehicle: str = "") -> ParsedNote:
        if os.environ.get("TALLER_NO_LLM") == "1":
            raise NoteParserUnavailableException("la IA está desactivada (TALLER_NO_LLM=1)")
        vehicle = clean_vehicle(vehicle)
        try:
            data = _ask_ollama(note, vehicle=vehicle)
            service = " ".join(str(data.get("service", "")).split())
            if service.lower() in GENERIC_SERVICES:
                service = ""
            result = ParsedNote(
                service=service or parse_with_rules(note).service,
                vehicle=vehicle or clean_vehicle(data.get("vehicle")),
                repeat_months=int(data.get("repeat_months", 0) or 0),
                parts=clean_parts(data.get("parts")),
                engine=f"ollama:{OLLAMA_MODEL}",
            )
        except Exception as exc:  # Ollama apagado o respuesta inválida
            raise NoteParserUnavailableException(explain_error(exc)) from exc
        if not result.service:
            raise NoteParserUnavailableException("Gemma no devolvió una respuesta válida")
        return result
