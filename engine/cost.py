"""Clasificación de horas y costo estimado de un cuadro."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from engine.models import Assignment, RosterProblem, RosterProposal

CATEGORIES = ("ordinary_day", "ordinary_night", "holiday_day", "holiday_night")


@dataclass
class HoursBreakdown:
    ordinary_day: int = 0
    ordinary_night: int = 0
    holiday_day: int = 0
    holiday_night: int = 0

    @property
    def total(self) -> int:
        return sum(getattr(self, c) for c in CATEGORIES)

    def add(self, other: "HoursBreakdown") -> None:
        for c in CATEGORIES:
            setattr(self, c, getattr(self, c) + getattr(other, c))


@dataclass
class CostSummary:
    base: float = 0.0
    night_surcharge: float = 0.0
    holiday_surcharge: float = 0.0
    hours: HoursBreakdown = field(default_factory=HoursBreakdown)
    by_employee: dict[str, "CostSummary"] = field(default_factory=dict)

    @property
    def surcharges(self) -> float:
        return self.night_surcharge + self.holiday_surcharge

    @property
    def total(self) -> float:
        return self.base + self.surcharges


def classify_hours(problem: RosterProblem, assignment: Assignment) -> HoursBreakdown:
    rules = problem.cost_rules
    shift = problem.shift(assignment.shift_code)
    start_date = problem.date_of(assignment.day)
    result = HoursBreakdown()
    if rules is None or start_date is None:
        result.ordinary_day = shift.hours
        return result
    current = datetime.combine(start_date, datetime.min.time()) + timedelta(hours=shift.start_hour)
    for _ in range(shift.hours):
        is_night = current.hour >= rules.night_start or current.hour < rules.day_start
        is_holiday = current.weekday() == 6 or current.date() in problem.holidays
        key = ("holiday_" if is_holiday else "ordinary_") + ("night" if is_night else "day")
        setattr(result, key, getattr(result, key) + 1)
        current += timedelta(hours=1)
    return result


def hourly_rate(problem: RosterProblem, employee_id: str) -> float:
    divisor = problem.cost_rules.monthly_hours_divisor if problem.cost_rules else 1
    return problem.employee(employee_id).monthly_salary / divisor


def assignment_cost(problem: RosterProblem, assignment: Assignment) -> CostSummary:
    rules = problem.cost_rules
    hours = classify_hours(problem, assignment)
    rate = hourly_rate(problem, assignment.employee_id)
    night = rules.night_surcharge if rules else 0.0
    holiday = rules.sunday_holiday_surcharge if rules else 0.0
    night_hours = hours.ordinary_night + hours.holiday_night
    holiday_hours = hours.holiday_day + hours.holiday_night
    return CostSummary(
        base=rate * hours.total,
        night_surcharge=rate * night * night_hours,
        holiday_surcharge=rate * holiday * holiday_hours,
        hours=hours,
    )


def surcharge_units(problem: RosterProblem, employee_id: str, day: int, shift_code: str) -> int:
    """Recargo en miles de pesos, entero, para usar en la función objetivo."""
    cost = assignment_cost(problem, Assignment(employee_id, day, shift_code, ""))
    return round(cost.surcharges / 1000)


def roster_cost(problem: RosterProblem, proposal: RosterProposal) -> CostSummary:
    summary = CostSummary()
    for a in proposal.assignments:
        item = assignment_cost(problem, a)
        per_emp = summary.by_employee.setdefault(a.employee_id, CostSummary())
        for target in (summary, per_emp):
            target.base += item.base
            target.night_surcharge += item.night_surcharge
            target.holiday_surcharge += item.holiday_surcharge
            target.hours.add(item.hours)
    return summary
