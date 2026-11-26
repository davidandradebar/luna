"""Intenciones que el bot convertirá en acciones estructuradas.

El intérprete de lenguaje solo traduce el mensaje a una intención; nunca
asigna turnos. El motor decide.
"""

from enum import StrEnum


class Intent(StrEnum):
    REGISTER_PREFERENCE = "register_preference"
    REQUEST_DAY_OFF = "request_day_off"
    REQUEST_SWAP = "request_swap"
    REPORT_ABSENCE = "report_absence"
    QUERY_SHIFT = "query_shift"
    QUERY_HOURS = "query_hours"
