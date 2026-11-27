from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import StrEnum


class PreferenceKind(StrEnum):
    PREFER_SHIFT = "prefer_shift"  # "prefiero noches"
    AVOID_SHIFT = "avoid_shift"  # "no me gustan las noches"
    AVOID_WEEKDAY = "avoid_weekday"  # "evitar domingos"
    DAY_OFF = "day_off"  # "libre el 15"


@dataclass(frozen=True)
class ShiftType:
    code: str
    start: str
    end: str
    hours: int
    crosses_midnight: bool = False
    label: str = ""

    @property
    def start_hour(self) -> int:
        return int(self.start.split(":")[0])


@dataclass(frozen=True)
class Employee:
    id: str
    role: str
    competencies: frozenset[str] = field(default_factory=frozenset)
    name: str = ""
    monthly_salary: int = 0
    # Prioridad por equidad histórica: mayor si el mes anterior se le cumplieron pocas preferencias.
    priority: float = 0.0
    min_hours: int | None = None  # horas mínimas del periodo según contrato

    @property
    def display_name(self) -> str:
        return self.name or self.id


@dataclass(frozen=True)
class CoverageRequirement:
    service: str
    day: int
    shift_code: str
    role: str
    minimum: int


@dataclass(frozen=True)
class Unavailability:
    employee_id: str
    day: int
    shift_code: str | None = None  # None = todo el día
    reason: str = ""


@dataclass(frozen=True)
class Preference:
    employee_id: str
    kind: PreferenceKind
    value: str | int  # código de turno, día de la semana (0=lunes) o día del periodo
    weight: int = 1
    note: str = ""


@dataclass(frozen=True)
class CostRules:
    """Parámetros de costo resueltos desde la tabla de reglas laborales."""

    monthly_hours_divisor: int
    night_start: int
    day_start: int
    night_surcharge: float
    sunday_holiday_surcharge: float


@dataclass(frozen=True)
class Strategy:
    key: str
    label: str
    description: str
    preference_weight: int
    fairness_weight: int
    cost_weight: int


@dataclass
class RosterProblem:
    days: int
    employees: list[Employee]
    shift_types: list[ShiftType]
    coverage: list[CoverageRequirement]
    unavailability: list[Unavailability] = field(default_factory=list)
    preferences: list[Preference] = field(default_factory=list)
    start_date: date | None = None
    holidays: frozenset[date] = field(default_factory=frozenset)
    # Límites que vienen de la tabla de reglas laborales del tenant, nunca fijos aquí.
    max_hours_per_employee: int | None = None
    max_weekly_hours: int | None = None
    max_consecutive_nights: int | None = None
    max_consecutive_work_days: int | None = None
    night_shift_codes: frozenset[str] = field(default_factory=frozenset)
    forbidden_sequences: list[tuple[str, str]] = field(default_factory=list)
    cost_rules: CostRules | None = None

    def date_of(self, day: int) -> date | None:
        return self.start_date + timedelta(days=day) if self.start_date else None

    def weekday_of(self, day: int) -> int:
        current = self.date_of(day)
        return current.weekday() if current else day % 7

    def is_sunday_or_holiday(self, day: int) -> bool:
        current = self.date_of(day)
        return current is not None and (current.weekday() == 6 or current in self.holidays)

    def weeks(self) -> list[list[int]]:
        """Días agrupados por semana calendario (lunes a domingo)."""
        groups: dict[int, list[int]] = {}
        offset = self.weekday_of(0)
        for d in range(self.days):
            groups.setdefault((d + offset) // 7, []).append(d)
        return list(groups.values())

    def employee(self, employee_id: str) -> Employee:
        return next(e for e in self.employees if e.id == employee_id)

    def shift(self, code: str) -> ShiftType:
        return next(s for s in self.shift_types if s.code == code)


@dataclass
class Assignment:
    employee_id: str
    day: int
    shift_code: str
    service: str


@dataclass
class RosterProposal:
    assignments: list[Assignment]
    objective: float
    strategy: Strategy | None = None
    solve_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "objective": self.objective,
            "strategy": self.strategy.key if self.strategy else None,
            "assignments": [a.__dict__ for a in self.assignments],
        }

    def for_employee(self, employee_id: str) -> list[Assignment]:
        return sorted((a for a in self.assignments if a.employee_id == employee_id), key=lambda a: a.day)

    def at(self, employee_id: str, day: int) -> Assignment | None:
        return next((a for a in self.assignments if a.employee_id == employee_id and a.day == day), None)
