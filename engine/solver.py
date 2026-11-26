"""Esqueleto del modelo CP-SAT.

Restricciones duras: cobertura mínima con competencia, un turno por día,
indisponibilidad, horas máximas y secuencias prohibidas (descanso).
Objetivo provisional: equilibrar horas. Preferencias y equidad se suman
como términos ponderados en iteraciones siguientes.
"""

from ortools.sat.python import cp_model

from engine.models import Assignment, RosterProblem, RosterProposal


def solve(
    problem: RosterProblem, max_solutions: int = 3, time_limit_s: float = 10.0
) -> list[RosterProposal]:
    model = cp_model.CpModel()
    shifts = {s.code: s for s in problem.shift_types}
    services = sorted({c.service for c in problem.coverage})

    # x[e, d, s, svc] = 1 si el empleado e trabaja el turno s del día d en el servicio svc
    x: dict[tuple[str, int, str, str], cp_model.IntVar] = {}
    for emp in problem.employees:
        for d in range(problem.days):
            for code in shifts:
                for svc in services:
                    if svc in emp.competencies:
                        x[emp.id, d, code, svc] = model.new_bool_var(f"x_{emp.id}_{d}_{code}_{svc}")

    def worked(emp_id: str, d: int, code: str | None = None) -> list[cp_model.IntVar]:
        return [
            v
            for (e, day, s, _), v in x.items()
            if e == emp_id and day == d and (code is None or s == code)
        ]

    roles = {e.id: e.role for e in problem.employees}

    for req in problem.coverage:
        model.add(
            sum(
                v
                for (e, d, s, svc), v in x.items()
                if d == req.day
                and s == req.shift_code
                and svc == req.service
                and roles[e] == req.role
            )
            >= req.minimum
        )

    for emp in problem.employees:
        for d in range(problem.days):
            model.add_at_most_one(worked(emp.id, d))

    for u in problem.unavailability:
        for v in worked(u.employee_id, u.day, u.shift_code):
            model.add(v == 0)

    hours_by_emp = {}
    for emp in problem.employees:
        hours = sum(shifts[s].hours * v for (e, _, s, _), v in x.items() if e == emp.id)
        hours_by_emp[emp.id] = hours
        if problem.max_hours_per_employee is not None:
            model.add(hours <= problem.max_hours_per_employee)

    for first, second in problem.forbidden_sequences:
        for emp in problem.employees:
            for d in range(problem.days - 1):
                for a in worked(emp.id, d, first):
                    for b in worked(emp.id, d + 1, second):
                        model.add_bool_or([a.Not(), b.Not()])

    max_hours = model.new_int_var(0, 24 * problem.days, "max_hours")
    for hours in hours_by_emp.values():
        model.add(hours <= max_hours)
    model.minimize(max_hours)

    proposals: list[RosterProposal] = []
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    for _ in range(max_solutions):
        status = solver.solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            break
        chosen = [key for key, v in x.items() if solver.value(v)]
        proposals.append(
            RosterProposal(
                assignments=[Assignment(e, d, s, svc) for e, d, s, svc in chosen],
                objective=solver.objective_value,
            )
        )
        # Excluir esta solución para obtener una alternativa distinta.
        model.add_bool_or([x[key].Not() for key in chosen])
    return proposals
