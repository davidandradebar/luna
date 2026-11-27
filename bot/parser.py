"""Intérprete simple de mensajes para la demo.

En producción este paso lo hace un modelo de lenguaje que solo traduce el
mensaje a una intención estructurada; nunca asigna turnos.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta

from bot.intents import Intent

WEEKDAYS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
# Frases que expresan rechazo: "no me gustan", "prefiero evitar", "no quiero", "prefiero no".
NEGATIVE = r"\bno (me )?gusta|evitar|\bno quiero|prefier\w* no\b|\bodio\b|\bdetesto\b|\bsin\b"
SHIFT_WORDS = {"noche": "N", "noches": "N", "manana": "M", "mananas": "M", "tarde": "T", "tardes": "T"}


@dataclass
class ParsedMessage:
    intent: Intent | None
    day: date | None = None
    shift_code: str | None = None
    weekday: int | None = None
    other_name: str | None = None
    extra: dict = field(default_factory=dict)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def parse_day(text: str, today: date) -> date | None:
    if "pasado manana" in text:
        return today + timedelta(days=2)
    if re.search(r"\bhoy\b", text):
        return today
    if re.search(r"\bmanana\b", text) and not re.search(r"\b(la|en la|por la|de la) manana\b", text):
        return today + timedelta(days=1)
    match = re.search(r"\b(?:el|del|dia)\s+(\d{1,2})\b", text)
    if match:
        try:
            return today.replace(day=int(match.group(1)))
        except ValueError:
            return None
    for i, name in enumerate(WEEKDAYS):
        if re.search(rf"\b{name}\b", text):
            delta = (i - today.weekday()) % 7
            return today + timedelta(days=delta)
    return None


def parse_message(text: str, today: date, names: list[str] | None = None) -> ParsedMessage:
    t = normalize(text)
    day = parse_day(t, today)
    other = None
    for name in names or []:
        first = normalize(name).replace("dra. ", "").replace("dr. ", "").split()[0]
        if re.search(rf"\b{re.escape(first)}\b", t):
            other = name
            break

    if re.search(r"por ?que me (toco|tocaron|pusieron|asignaron)", t):
        return ParsedMessage(Intent.EXPLAIN_SHIFT, day=day or today)
    if re.search(r"cambi|intercambi|cambalache", t):
        return ParsedMessage(Intent.REQUEST_SWAP, day=day, other_name=other)
    if re.search(r"incapacid|calamidad|no puedo ir|no voy a poder|enferm", t):
        return ParsedMessage(Intent.REPORT_ABSENCE, day=day or today)
    if re.search(r"cuant\w* horas", t):
        return ParsedMessage(Intent.QUERY_HOURS)
    if re.search(r"\blibre\b|descans", t) and day:
        return ParsedMessage(Intent.REQUEST_DAY_OFF, day=day)
    if re.search(r"prefier|me gusta\w*|evitar|no quiero|odio|detesto", t):
        avoid = bool(re.search(NEGATIVE, t))
        for word, code in SHIFT_WORDS.items():
            if re.search(rf"\b{word}\b", t):
                return ParsedMessage(Intent.REGISTER_PREFERENCE, shift_code=code, extra={"avoid": avoid})
        for i, name in enumerate(WEEKDAYS):
            if re.search(rf"\b{name}s?\b", t):
                return ParsedMessage(Intent.REGISTER_PREFERENCE, weekday=i, extra={"avoid": avoid})
    if re.search(r"turno|trabaj|me toca", t):
        return ParsedMessage(Intent.QUERY_SHIFT, day=day or today)
    return ParsedMessage(None)
