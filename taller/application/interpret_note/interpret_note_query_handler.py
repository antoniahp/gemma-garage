from taller.domain.note_parser import NoteParser
from taller.domain.parsed_note import ParsedNote

from taller.application.interpret_note.interpret_note_query import InterpretNoteQuery


class InterpretNoteQueryHandler:
    def __init__(self, note_parser: NoteParser):
        self.note_parser = note_parser

    def handle(self, query: InterpretNoteQuery) -> ParsedNote:
        return self.note_parser.parse(query.note, vehicle=query.vehicle)
