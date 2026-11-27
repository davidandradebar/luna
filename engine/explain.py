"""Explicación en lenguaje sencillo de "¿por qué me tocó esto?"."""

from statistics import mean

from engine.checks import blocking_reasons
from engine.metrics import employee_loads
from engine.models import PreferenceKind, RosterProblem, RosterProposal

WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _preference_lines(problem: RosterProblem, employee_id: str, day: int, shift_code: str | None):
    lines = []
    for pref in problem.preferences:
        if pref.employee_id != employee_id:
            continue
        if pref.kind == PreferenceKind.DAY_OFF and int(pref.value) == day:
            ok = shift_code is None
            lines.append(f"Pidió este día libre: {'se cumplió' if ok else 'no se pudo cumplir'}.")
        elif pref.kind == PreferenceKind.AVOID_WEEKDAY and problem.weekday_of(day) == int(pref.value):
            ok = shift_code is None
            lines.append(
                f"Prefiere evitar los {WEEKDAYS[int(pref.value)]}: "
                + ("cumplido." if ok else "esta vez le tocó.")
            )
        elif pref.kind == PreferenceKind.AVOID_SHIFT and shift_code == pref.value:
            lines.append(
                f"Prefiere evitar este horario ({pref.note.lower()}); este turno se necesitaba "
                "para completar la cobertura."
            )
        elif pref.kind == PreferenceKind.PREFER_SHIFT and shift_code:
            if shift_code == pref.value:
                lines.append(f"Coincide con su preferencia ({pref.note.lower()}).")
            else:
                lines.append(
                    f"Su preferencia es otra ({pref.note.lower()}); este turno se necesitaba "
                    "para completar la cobertura."
                )
    return lines


def explain(problem: RosterProblem, proposal: RosterProposal, employee_id: str, day: int) -> dict:
    emp = problem.employee(employee_id)
    assignment = proposal.at(employee_id, day)
    loads = employee_loads(problem, proposal)
    load = loads[employee_id]
    peers = [loads[e.id] for e in problem.employees if e.role == emp.role]
    lines: list[str] = []

    if assignment is None:
        title = "Día libre"
        for u in problem.unavailability:
            if u.employee_id == employee_id and u.day == day and u.shift_code is None:
                lines.append(f"Tiene una novedad registrada: {u.reason}.")
        prev = proposal.at(employee_id, day - 1)
        if prev and any(first == prev.shift_code for first, _ in problem.forbidden_sequences):
            lines.append("Descansa porque el día anterior hizo noche.")
        lines += _preference_lines(problem, employee_id, day, None)
        if not lines:
            lines.append("La cobertura del día ya estaba completa con el resto del equipo.")
    else:
        shift = problem.shift(assignment.shift_code)
        title = f"Turno {shift.label or shift.code} ({shift.start}–{shift.end})"
        need = next(
            (
                c.minimum
                for c in problem.coverage
                if c.day == day
                and c.shift_code == assignment.shift_code
                and c.service == assignment.service
                and c.role == emp.role
            ),
            None,
        )
        if need:
            people = "1 persona" if need == 1 else f"{need} personas"
            lines.append(f"El servicio necesitaba {people} de su cargo en este turno.")
        lines.append("Tiene la formación y la habilitación para este servicio.")
        lines += _preference_lines(problem, employee_id, day, assignment.shift_code)
        others = [
            e.id
            for e in problem.employees
            if e.role == emp.role
            and e.id != employee_id
            and not blocking_reasons(problem, proposal, e.id, day, assignment.shift_code, assignment.service)
        ]
        if not others:
            lines.append("Nadie más de su cargo podía cubrirlo sin romper una regla.")
        if assignment.shift_code in problem.night_shift_codes:
            avg = mean(p.nights for p in peers)
            lines.append(f"Lleva {load.nights} noches en el mes; el promedio de su cargo es {avg:.1f}.")
        if problem.is_sunday_or_holiday(day):
            avg = mean(p.sundays_holidays for p in peers)
            lines.append(
                f"Lleva {load.sundays_holidays} domingos/festivos; el promedio de su cargo es {avg:.1f}."
            )
        lines.append("Se respetan su descanso y el máximo de horas semanales.")

    return {
        "employee": emp.display_name,
        "title": title,
        "month_hours": load.hours,
        "lines": lines,
    }
