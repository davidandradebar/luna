from datetime import date

from bot.intents import Intent
from bot.parser import parse_message

TODAY = date(2026, 12, 3)  # jueves


def test_query_shift_weekday():
    parsed = parse_message("¿Qué turno tengo el viernes?", TODAY)
    assert parsed.intent == Intent.QUERY_SHIFT
    assert parsed.day == date(2026, 12, 4)


def test_query_hours():
    assert parse_message("cuántas horas llevo?", TODAY).intent == Intent.QUERY_HOURS


def test_day_off_by_number():
    parsed = parse_message("necesito el 15 libre", TODAY)
    assert parsed.intent == Intent.REQUEST_DAY_OFF
    assert parsed.day == date(2026, 12, 15)


def test_absence_defaults_to_today():
    parsed = parse_message("tengo incapacidad, no puedo ir", TODAY)
    assert parsed.intent == Intent.REPORT_ABSENCE
    assert parsed.day == TODAY


def test_swap_with_named_colleague():
    parsed = parse_message("quiero cambiar mi turno del 12 con Laura", TODAY, ["Laura B.", "Mario G."])
    assert parsed.intent == Intent.REQUEST_SWAP
    assert parsed.day == date(2026, 12, 12)
    assert parsed.other_name == "Laura B."


def test_preference_for_nights():
    parsed = parse_message("prefiero las noches", TODAY)
    assert parsed.intent == Intent.REGISTER_PREFERENCE
    assert parsed.shift_code == "N"


def test_morning_word_is_not_tomorrow():
    parsed = parse_message("qué turno tengo mañana", TODAY)
    assert parsed.day == date(2026, 12, 4)
