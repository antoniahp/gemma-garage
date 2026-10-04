from dataclasses import replace

from taller.domain.note_cleaning import clean_vehicle
from taller.domain.note_parser import NoteParser, NoteParserUnavailableException
from taller.domain.parsed_note import ParsedNote


class NoteParserWithFallback(NoteParser):
    """Prueba primero el intérprete principal (Gemma); si no puede, usa el de respaldo (reglas).

    El taller nunca se queda parado, y el resultado dice por qué no se usó la IA (`llm_error`).
    """

    def __init__(self, primary: NoteParser, fallback: NoteParser):
        self.primary = primary
        self.fallback = fallback

    def parse(self, note: str, vehicle: str = "") -> ParsedNote:
        try:
            return self.primary.parse(note, vehicle=vehicle)
        except NoteParserUnavailableException as exc:
            return replace(self.fallback.parse(note, vehicle=clean_vehicle(vehicle)), llm_error=str(exc))
