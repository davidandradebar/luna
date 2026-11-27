"""Indicadores de un cuadro: preferencias cumplidas, equidad y cobertura."""

from dataclasses import dataclass
from statistics import mean

from engine.models import Preference, PreferenceKind, RosterProblem, RosterProposal

FULFILLED_THRESHOLD = 0.75


@dataclass
class PreferenceResult:
    preference: Preference
    score: float  # 0 a 1
    detail: str

    @property
    def fulfilled(self) -> bool:
        return self.score >= FULFILLED_THRESHOLD


def evaluate_preference(
    problem: RosterProblem, proposal: RosterProposal, pref: Preference
) -> PreferenceResult:
    mine = proposal.for_employee(pref.employee_id)
    if pref.kind == PreferenceKind.DAY_OFF:
        works = any(a.day == int(pref.value) for a in mine)
        return PreferenceResult(pref, 0.0 if works else 1.0, "Trabaja ese día" if works else "Libre")
    if pref.kind == PreferenceKind.AVOID_WEEKDAY:
        days = [d for d in range(problem.days) if problem.weekday_of(d) == int(pref.value)]
        worked = sum(1 for a in mine if a.day in days)
        score = 1 - worked / len(days) if days else 1.0
        return PreferenceResult(pref, score, f"Trabaja {worked} de {len(days)}")
    if pref.kind == PreferenceKind.AVOID_SHIFT:
        worked = sum(1 for a in mine if a.shift_code == pref.value)
        score = 1 - worked / len(mine) if mine else 1.0
        return PreferenceResult(pref, score, f"{worked} de {len(mine)} turnos en ese horario")
    matching = sum(1 for a in mine if a.shift_code == pref.value)
    score = matching / len(mine) if mine else 0.0
    return PreferenceResult(pref, score, f"{matching} de {len(mine)} turnos")


def preference_results(problem: RosterProblem, proposal: RosterProposal) -> list[PreferenceResult]:
    return [evaluate_preference(problem, proposal, p) for p in problem.preferences]


def preference_rate(results: list[PreferenceResult]) -> float:
    return sum(r.fulfilled for r in results) / len(results) if results else 1.0


@dataclass
class EmployeeLoad:
    employee_id: str
    shifts: int
    hours: int
    nights: int
    sundays_holidays: int


def employee_loads(problem: RosterProblem, proposal: RosterProposal) -> dict[str, EmployeeLoad]:
    loads = {e.id: EmployeeLoad(e.id, 0, 0, 0, 0) for e in problem.employees}
    for a in proposal.assignments:
        load = loads[a.employee_id]
        load.shifts += 1
        load.hours += problem.shift(a.shift_code).hours
        load.nights += a.shift_code in problem.night_shift_codes
        load.sundays_holidays += problem.is_sunday_or_holiday(a.day)
    return loads


@dataclass
class FairnessRow:
    role: str
    nights_min: int
    nights_max: int
    holidays_min: int
    holidays_max: int
    hours_min: int
    hours_max: int
    hours_avg: float


def night_lovers(problem: RosterProblem) -> set[str]:
    return {
        p.employee_id
        for p in problem.preferences
        if p.kind == PreferenceKind.PREFER_SHIFT and p.value in problem.night_shift_codes
    }


def fairness(problem: RosterProblem, proposal: RosterProposal) -> list[FairnessRow]:
    """Rangos por cargo. Las noches excluyen a quien pidió noches o no puede hacerlas."""
    loads = employee_loads(problem, proposal)
    lovers = night_lovers(problem)
    rows = []
    for role in dict.fromkeys(e.role for e in problem.employees):
        staff = [loads[e.id] for e in problem.employees if e.role == role]
        night_capable = [s for s in staff if s.nights and s.employee_id not in lovers] or staff
        rows.append(
            FairnessRow(
                role=role,
                nights_min=min(s.nights for s in night_capable),
                nights_max=max(s.nights for s in night_capable),
                holidays_min=min(s.sundays_holidays for s in staff),
                holidays_max=max(s.sundays_holidays for s in staff),
                hours_min=min(s.hours for s in staff),
                hours_max=max(s.hours for s in staff),
                hours_avg=round(mean(s.hours for s in staff), 1),
            )
        )
    return rows


def coverage_gaps(problem: RosterProblem, proposal: RosterProposal) -> list:
    """Requerimientos que no alcanzan el mínimo (p. ej. tras una novedad)."""
    roles = {e.id: e.role for e in problem.employees}
    counts: dict[tuple, int] = {}
    for a in proposal.assignments:
        key = (a.service, a.day, a.shift_code, roles[a.employee_id])
        counts[key] = counts.get(key, 0) + 1
    return [
        req
        for req in problem.coverage
        if counts.get((req.service, req.day, req.shift_code, req.role), 0) < req.minimum
    ]
