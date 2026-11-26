"""Validaciones puntuales sobre un cuadro ya generado (reemplazos e intercambios)."""

from dataclasses import dataclass

from engine.cost import assignment_cost
from engine.models import Assignment, RosterProblem, RosterProposal


def _week_of(problem: RosterProblem, day: int) -> list[int]:
    return next(w for w in problem.weeks() if day in w)


def blocking_reasons(
    problem: RosterProblem,
    proposal: RosterProposal,
    employee_id: str,
    day: int,
    shift_code: str,
    service: str,
    ignore: Assignment | None = None,
) -> list[str]:
    """Motivos por los que la persona NO puede tomar ese turno. Vacío = puede."""
    emp = problem.employee(employee_id)
    reasons = []
    if service not in emp.competencies:
        reasons.append("No está habilitado(a) para este servicio")
    mine = [a for a in proposal.for_employee(employee_id) if a is not ignore]
    by_day = {a.day: a for a in mine}
    if day in by_day:
        reasons.append("Ya tiene turno ese día")
    for u in problem.unavailability:
        if u.employee_id == employee_id and u.day == day and u.shift_code in (None, shift_code):
            reasons.append(f"No disponible: {u.reason or 'novedad registrada'}")
            break
    for first, second in problem.forbidden_sequences:
        prev, nxt = by_day.get(day - 1), by_day.get(day + 1)
        if prev and prev.shift_code == first and shift_code == second:
            reasons.append("Viene de una noche: necesita descanso")
        if nxt and shift_code == first and nxt.shift_code == second:
            reasons.append("Quedaría sin descanso antes de su turno siguiente")
    if problem.max_weekly_hours is not None:
        week = _week_of(problem, day)
        hours = sum(problem.shift(a.shift_code).hours for a in mine if a.day in week)
        if hours + problem.shift(shift_code).hours > problem.max_weekly_hours:
            reasons.append(f"Superaría {problem.max_weekly_hours} h en la semana")
    if problem.max_consecutive_work_days is not None:
        k = problem.max_consecutive_work_days
        run = 1
        d = day - 1
        while d in by_day:
            run, d = run + 1, d - 1
        d = day + 1
        while d in by_day:
            run, d = run + 1, d + 1
        if run > k:
            reasons.append(f"Superaría {k} días seguidos trabajando")
    if problem.max_consecutive_nights is not None and shift_code in problem.night_shift_codes:
        k = problem.max_consecutive_nights
        nights = {a.day for a in mine if a.shift_code in problem.night_shift_codes} | {day}
        run, d = 1, day - 1
        while d in nights:
            run, d = run + 1, d - 1
        d = day + 1
        while d in nights:
            run, d = run + 1, d + 1
        if run > k:
            reasons.append(f"Superaría {k} noches seguidas")
    return reasons


@dataclass
class Replacement:
    employee_id: str
    month_hours: int
    surcharge: float
    notes: list[str]


def suggest_replacements(
    problem: RosterProblem, proposal: RosterProposal, absent: Assignment, limit: int = 5
) -> list[Replacement]:
    role = problem.employee(absent.employee_id).role
    result = []
    for emp in problem.employees:
        if emp.id == absent.employee_id or emp.role != role:
            continue
        if blocking_reasons(problem, proposal, emp.id, absent.day, absent.shift_code, absent.service):
            continue
        hours = sum(problem.shift(a.shift_code).hours for a in proposal.for_employee(emp.id))
        cost = assignment_cost(problem, Assignment(emp.id, absent.day, absent.shift_code, ""))
        notes = ["Libre ese día", "Habilitado(a) para el servicio", "Cumple descanso y horas"]
        result.append(Replacement(emp.id, hours, cost.surcharges, notes))
    result.sort(key=lambda r: (r.month_hours, r.surcharge))
    return result[:limit]
