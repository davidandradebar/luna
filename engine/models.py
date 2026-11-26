from dataclasses import dataclass, field


@dataclass(frozen=True)
class ShiftType:
    code: str
    start: str
    end: str
    hours: int
    crosses_midnight: bool = False


@dataclass(frozen=True)
class Employee:
    id: str
    role: str
    competencies: frozenset[str] = field(default_factory=frozenset)


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


@dataclass
class RosterProblem:
    days: int
    employees: list[Employee]
    shift_types: list[ShiftType]
    coverage: list[CoverageRequirement]
    unavailability: list[Unavailability] = field(default_factory=list)
    # Límites que vienen de la tabla de reglas laborales del tenant, nunca fijos aquí.
    max_hours_per_employee: int | None = None
    forbidden_sequences: list[tuple[str, str]] = field(default_factory=list)


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

    def to_dict(self) -> dict:
        return {
            "objective": self.objective,
            "assignments": [a.__dict__ for a in self.assignments],
        }
