from engine.models import (
    CoverageRequirement,
    Employee,
    RosterProblem,
    ShiftType,
    Unavailability,
)
from engine.solver import solve


def _problem(**overrides) -> RosterProblem:
    base = dict(
        days=3,
        employees=[
            Employee("EMP-001", "auxiliar", frozenset({"urgencias"})),
            Employee("EMP-002", "auxiliar", frozenset({"urgencias"})),
            Employee("EMP-003", "auxiliar", frozenset({"urgencias"})),
        ],
        shift_types=[
            ShiftType("M", "07:00", "13:00", 6),
            ShiftType("N", "19:00", "07:00", 12, True),
        ],
        coverage=[
            CoverageRequirement("urgencias", d, code, "auxiliar", 1) for d in range(3) for code in ("M", "N")
        ],
    )
    base.update(overrides)
    return RosterProblem(**base)


def test_returns_up_to_three_distinct_proposals():
    proposals = solve(_problem())
    assert 1 <= len(proposals) <= 3
    signatures = {frozenset((a.employee_id, a.day, a.shift_code) for a in p.assignments) for p in proposals}
    assert len(signatures) == len(proposals)


def test_coverage_and_one_shift_per_day():
    proposal = solve(_problem(), max_solutions=1)[0]
    for d in range(3):
        for code in ("M", "N"):
            assert any(a.day == d and a.shift_code == code for a in proposal.assignments)
    seen = [(a.employee_id, a.day) for a in proposal.assignments]
    assert len(seen) == len(set(seen))


def test_unavailability_is_respected():
    problem = _problem(unavailability=[Unavailability("EMP-001", 0)])
    for proposal in solve(problem):
        assert not any(a.employee_id == "EMP-001" and a.day == 0 for a in proposal.assignments)


def test_forbidden_sequence_night_then_morning():
    problem = _problem(forbidden_sequences=[("N", "M")])
    for proposal in solve(problem):
        nights = {(a.employee_id, a.day) for a in proposal.assignments if a.shift_code == "N"}
        mornings = {(a.employee_id, a.day) for a in proposal.assignments if a.shift_code == "M"}
        assert not any((e, d + 1) in mornings for e, d in nights)


def test_infeasible_problem_returns_no_proposals():
    assert solve(_problem(max_hours_per_employee=6)) == []
