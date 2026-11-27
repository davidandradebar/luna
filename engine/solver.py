"""Modelo CP-SAT del cuadro de turnos.

Restricciones duras: cobertura exacta con competencia, un turno por día,
indisponibilidad y novedades, horas máximas (semana y periodo), noches y días
seguidos, y secuencias prohibidas (descanso después de noche).

Objetivo (pesos por estrategia): preferencias del equipo, equidad en noches y
domingos/festivos, y costo de recargos.
"""

import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from ortools.sat.python import cp_model

from engine.cost import surcharge_units
from engine.models import (
    Assignment,
    PreferenceKind,
    RosterProblem,
    RosterProposal,
    Strategy,
)

DEFAULT_STRATEGY = Strategy("default", "Base", "", 1, 1, 0)

STRATEGIES = [
    Strategy(
        "balanced",
        "Equilibrado",
        "Balancea preferencias, reparto justo y costo.",
        preference_weight=60,
        fairness_weight=40,
        cost_weight=1,
    ),
    Strategy(
        "preferences",
        "Preferencias primero",
        "Cumple la mayor cantidad de preferencias del equipo.",
        preference_weight=40,
        fairness_weight=10,
        cost_weight=0,
    ),
    Strategy(
        "cost",
        "Menor costo",
        "Reduce recargos nocturnos y dominicales sin romper reglas.",
        preference_weight=4,
        fairness_weight=4,
        cost_weight=6,
    ),
]

Key = tuple[str, int, str, str]  # (empleado, día, turno, servicio)


class _Model:
    def __init__(self, problem: RosterProblem):
        self.problem = problem
        self.model = cp_model.CpModel()
        self.x: dict[Key, cp_model.IntVar] = {}
        self.by_emp_day: dict[tuple[str, int], list[tuple[str, cp_model.IntVar]]] = defaultdict(list)
        self._build_variables()
        self._add_hard_constraints()

    def _build_variables(self) -> None:
        needed = {(c.service, c.day, c.shift_code, c.role) for c in self.problem.coverage}
        blocked = {(u.employee_id, u.day, u.shift_code) for u in self.problem.unavailability}
        for svc, d, code, role in sorted(needed):
            for emp in self.problem.employees:
                if emp.role != role or svc not in emp.competencies:
                    continue
                if (emp.id, d, None) in blocked or (emp.id, d, code) in blocked:
                    continue
                var = self.model.new_bool_var(f"x_{emp.id}_{d}_{code}_{svc}")
                self.x[emp.id, d, code, svc] = var
                self.by_emp_day[emp.id, d].append((code, var))

    def worked(self, emp_id: str, d: int, codes: set[str] | None = None) -> list:
        return [v for code, v in self.by_emp_day.get((emp_id, d), []) if not codes or code in codes]

    def hours(self, emp_id: str, days) -> cp_model.LinearExpr:
        p = self.problem
        return sum(p.shift(code).hours * v for d in days for code, v in self.by_emp_day[emp_id, d])

    def _add_hard_constraints(self) -> None:
        p, m = self.problem, self.model
        roles = {e.id: e.role for e in p.employees}
        slots: dict[tuple, list] = defaultdict(list)
        for (e, d, code, svc), v in self.x.items():
            slots[svc, d, code, roles[e]].append(v)
        for req in p.coverage:
            m.add(sum(slots[req.service, req.day, req.shift_code, req.role]) == req.minimum)

        nights = set(p.night_shift_codes)
        for emp in p.employees:
            for d in range(p.days):
                m.add_at_most_one(self.worked(emp.id, d))
            if emp.min_hours is not None:
                m.add(self.hours(emp.id, range(p.days)) >= emp.min_hours)
            if p.max_hours_per_employee is not None:
                m.add(self.hours(emp.id, range(p.days)) <= p.max_hours_per_employee)
            if p.max_weekly_hours is not None:
                for week in p.weeks():
                    m.add(self.hours(emp.id, week) <= p.max_weekly_hours)
            if p.max_consecutive_nights is not None and nights:
                k = p.max_consecutive_nights
                for start in range(p.days - k):
                    window = [v for d in range(start, start + k + 1) for v in self.worked(emp.id, d, nights)]
                    m.add(sum(window) <= k)
            if p.max_consecutive_work_days is not None:
                k = p.max_consecutive_work_days
                for start in range(p.days - k):
                    window = [v for d in range(start, start + k + 1) for v in self.worked(emp.id, d)]
                    m.add(sum(window) <= k)
            for first, second in p.forbidden_sequences:
                for d in range(p.days - 1):
                    for a in self.worked(emp.id, d, {first}):
                        for b in self.worked(emp.id, d + 1, {second}):
                            m.add_bool_or([a.Not(), b.Not()])

    def set_objective(self, strategy: Strategy) -> None:
        p, m = self.problem, self.model
        terms = []

        for pref in p.preferences:
            emp = p.employee(pref.employee_id)
            weight = round(strategy.preference_weight * pref.weight * (1 + emp.priority))
            if pref.kind == PreferenceKind.PREFER_SHIFT:
                others = [
                    v for d in range(p.days) for code, v in self.by_emp_day[emp.id, d] if code != pref.value
                ]
                terms.append(-weight * sum(others))
            elif pref.kind == PreferenceKind.AVOID_SHIFT:
                same = [
                    v for d in range(p.days) for code, v in self.by_emp_day[emp.id, d] if code == pref.value
                ]
                terms.append(-weight * sum(same))
            elif pref.kind == PreferenceKind.AVOID_WEEKDAY:
                days = [d for d in range(p.days) if p.weekday_of(d) == int(pref.value)]
                terms.append(-weight * sum(v for d in days for v in self.worked(emp.id, d)))
            elif pref.kind == PreferenceKind.DAY_OFF:
                terms.append(-5 * weight * sum(self.worked(emp.id, int(pref.value))))

        if strategy.fairness_weight:
            nights = set(p.night_shift_codes)
            holidays = [d for d in range(p.days) if p.is_sunday_or_holiday(d)]
            likes_nights = {
                pref.employee_id
                for pref in p.preferences
                if pref.kind == PreferenceKind.PREFER_SHIFT and pref.value in nights
            }
            for role in sorted({e.role for e in p.employees}):
                staff = [e for e in p.employees if e.role == role]
                for label, counter, group in (
                    (
                        "n",
                        lambda e: [v for d in range(p.days) for v in self.worked(e.id, d, nights)],
                        [e for e in staff if e.id not in likes_nights],
                    ),
                    ("h", lambda e: [v for d in holidays for v in self.worked(e.id, d)], staff),
                ):
                    counts = [sum(counter(e)) for e in group if counter(e)]
                    if len(counts) < 2:
                        continue
                    hi = m.new_int_var(0, p.days, f"max_{label}_{role}")
                    lo = m.new_int_var(0, p.days, f"min_{label}_{role}")
                    for c in counts:
                        m.add(c <= hi)
                        m.add(c >= lo)
                    terms.append(-strategy.fairness_weight * (hi - lo))
                hours = [self.hours(e.id, range(p.days)) for e in staff]
                if len(hours) >= 2:
                    hi = m.new_int_var(0, 24 * p.days, f"max_hours_{role}")
                    lo = m.new_int_var(0, 24 * p.days, f"min_hours_{role}")
                    for h in hours:
                        m.add(h <= hi)
                        m.add(h >= lo)
                    terms.append(-(strategy.fairness_weight // 3 or 1) * (hi - lo))

        if strategy.cost_weight and p.cost_rules is not None:
            terms.append(
                -strategy.cost_weight
                * sum(surcharge_units(p, e, d, code) * v for (e, d, code, _), v in self.x.items())
            )

        m.maximize(sum(terms))

    def run(self, time_limit_s: float, workers: int = 8):
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit_s
        solver.parameters.num_workers = workers
        solver.parameters.random_seed = 7
        status = solver.solve(self.model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return None, []
        chosen = [k for k, v in self.x.items() if solver.value(v)]
        return solver, chosen


def _to_proposal(chosen: list[Key], objective: float, strategy, seconds: float) -> RosterProposal:
    return RosterProposal(
        assignments=[Assignment(e, d, s, svc) for e, d, s, svc in chosen],
        objective=objective,
        strategy=strategy,
        solve_seconds=seconds,
    )


def solve(problem: RosterProblem, max_solutions: int = 3, time_limit_s: float = 10.0) -> list[RosterProposal]:
    """Soluciones distintas con el mismo objetivo (excluye cada solución encontrada)."""
    built = _Model(problem)
    built.set_objective(DEFAULT_STRATEGY)
    proposals: list[RosterProposal] = []
    for _ in range(max_solutions):
        started = time.perf_counter()
        solver, chosen = built.run(time_limit_s)
        if solver is None:
            break
        proposals.append(_to_proposal(chosen, solver.objective_value, None, time.perf_counter() - started))
        built.model.add_bool_or([built.x[k].Not() for k in chosen])
    return proposals


def solve_strategy(
    problem: RosterProblem, strategy: Strategy, time_limit_s: float = 8.0, workers: int = 8
) -> RosterProposal | None:
    started = time.perf_counter()
    built = _Model(problem)
    built.set_objective(strategy)
    solver, chosen = built.run(time_limit_s, workers)
    if solver is None:
        return None
    return _to_proposal(chosen, solver.objective_value, strategy, time.perf_counter() - started)


def solve_strategies(
    problem: RosterProblem, strategies: list[Strategy] = STRATEGIES, time_limit_s: float = 8.0
) -> list[RosterProposal]:
    """Genera una propuesta por estrategia, en paralelo."""
    with ThreadPoolExecutor(max_workers=len(strategies)) as pool:
        results = pool.map(lambda s: solve_strategy(problem, s, time_limit_s, workers=4), strategies)
    return [r for r in results if r is not None]
