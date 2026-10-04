from abc import ABC, abstractmethod

from taller.domain.parsed_note import ParsedNote


class NoteParserUnavailableException(Exception):
    """El intérprete no pudo responder (p. ej. Ollama apagado). El mensaje explica por qué."""


class NoteParser(ABC):
    @abstractmethod
    def parse(self, note: str, vehicle: str = "") -> ParsedNote:
        raise NotImplementedError
