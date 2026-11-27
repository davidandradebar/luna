from datetime import date

import pytest

from app import create_app
from app.config import TestConfig
from app.demo.data import ClinicData
from app.demo.state import reset_state
from engine.checks import blocking_reasons, legal_alerts, suggest_replacements
from engine.cost import classify_hours, roster_cost
from engine.explain import explain
from engine.metrics import coverage_gaps, preference_rate, preference_results
from engine.models import Assignment
from engine.solver import solve_strategies


@pytest.fixture(scope="module")
def solved():
    problem = ClinicData.load().problem()
    return problem, solve_strategies(problem, time_limit_s=3)


def test_demo_problem_uses_rules_table():
    clinic = ClinicData.load()
    problem = clinic.problem()
    assert problem.max_weekly_hours == clinic.legal_max_weekly_hours()
    assert problem.cost_rules.night_surcharge == pytest.approx(0.35)
    assert len(problem.employees) == 25


def test_clinic_policy_cannot_exceed_legal_maximum():
    clinic = ClinicData.load()
    clinic.policy["max_weekly_hours"] = 60
    assert clinic.problem().max_weekly_hours == clinic.legal_max_weekly_hours()


def test_three_proposals_with_full_coverage(solved):
    problem, proposals = solved
    assert [p.strategy.key for p in proposals] == ["balanced", "preferences", "cost"]
    for proposal in proposals:
        assert coverage_gaps(problem, proposal) == []
        assert 0 <= preference_rate(preference_results(problem, proposal)) <= 1


def test_generated_rosters_have_no_legal_alerts(solved):
    problem, proposals = solved
    for proposal in proposals:
        assert legal_alerts(problem, proposal) == []


def test_cost_strategy_beats_strategy_that_ignores_cost(solved):
    # Con límite de tiempo el motor no garantiza el óptimo global; sí debe ganarle
    # a la versión que no pondera el costo.
    problem, proposals = solved
    costs = {p.strategy.key: roster_cost(problem, p).total for p in proposals}
    assert costs["cost"] < costs["preferences"]


def test_night_shift_hours_split_across_sunday():
    problem = ClinicData.load().problem()
    saturday = (date(2026, 12, 5) - problem.start_date).days
    hours = classify_hours(problem, Assignment("EMP-001", saturday, "N", "agudos"))
    assert (hours.ordinary_night, hours.holiday_night, hours.holiday_day) == (5, 6, 1)


def test_replacements_are_legal(solved):
    problem, proposals = solved
    proposal = proposals[0]
    absent = proposal.assignments[0]
    for option in suggest_replacements(problem, proposal, absent):
        assert not blocking_reasons(
            problem, proposal, option.employee_id, absent.day, absent.shift_code, absent.service
        )


def test_explanation_has_reasons(solved):
    problem, proposals = solved
    a = proposals[0].assignments[0]
    result = explain(problem, proposals[0], a.employee_id, a.day)
    assert result["title"].startswith("Turno")
    assert result["lines"]


def test_guided_flow_end_to_end():
    reset_state()
    client = create_app(TestConfig).test_client()
    for url in ("/", "/clinica", "/equipo", "/generar", "/whatsapp"):
        assert client.get(url).status_code == 200
    assert client.post("/generar").status_code == 302
    home = client.get("/").get_data(as_text=True)
    assert "Alertas legales" in home and "Aprobar y publicar" in home
    assert client.get("/?v=2").status_code == 200
    assert client.get("/comparar").status_code == 200
    assert client.get("/cuadro/0").status_code == 200
    assert client.get("/api/explicar/0/EMP-001/0").get_json()["lines"]
    assert client.post("/publicar/0").status_code == 302
    assert client.get("/publicado").status_code == 200
    answer = client.post(
        "/api/whatsapp", json={"employee_id": "EMP-001", "text": "¿cuántas horas llevo?"}
    ).get_json()
    assert "horas" in answer["reply"]
    export = client.get("/exportar/0")
    assert export.status_code == 200
    assert export.data[:2] == b"PK"
    reset_state()


def test_valid_swap_request_can_be_approved():
    from app.demo.requests import swap_requests
    from app.demo.state import get_state

    reset_state()
    client = create_app(TestConfig).test_client()
    client.post("/generar")
    state = get_state()
    requests = swap_requests(state, 0)
    valid = next(r for r in requests if r.check.valid)
    response = client.post(
        "/solicitudes/cambio",
        data={
            "index": 0,
            "key": valid.key,
            "requester": valid.requester,
            "other": valid.other,
            "day": valid.day,
        },
    )
    assert response.status_code == 302
    assert state.proposals[0].at(valid.other, valid.day) is not None
    assert state.proposals[0].at(valid.requester, valid.day) is None
    assert legal_alerts(state.problem, state.proposals[0]) == []
    reset_state()
