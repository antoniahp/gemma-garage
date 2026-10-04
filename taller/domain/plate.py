import re


def normalize_plate(text):
    """"1234 bcd" y "1234-BCD" son la misma matrícula."""
    return re.sub(r"[^A-Z0-9]", "", (text or "").upper())
