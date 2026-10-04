"""Bandeja de salida local: sin configuración, nada sale al exterior (se guarda aquí para poder probar)."""

import json
import os
from datetime import datetime

from django.conf import settings


def append(filename, record):
    os.makedirs(settings.TALLER_OUTBOX, exist_ok=True)
    record = {"at": datetime.now().isoformat(timespec="seconds"), **record}
    with open(os.path.join(settings.TALLER_OUTBOX, filename), "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def format_parts(parts):
    lines = []
    for p in parts:
        spec = f" {p['spec']}" if p.get("spec") else ""
        lines.append(f"- {p['qty']} {p.get('unit', 'ud')} de {p['name']}{spec}")
    return "\n".join(lines)
