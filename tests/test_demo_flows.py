"""Flujos de la demo que deben funcionar en la presentación."""

from datetime import date

import pytest

from app import create_app
from app.config import TestConfig
from app.demo.requests import pending_absences
from app.demo.state import get_state, reset_state
from app.demo.whatsapp import reply, suggestions_for
from app.routes.demo import whatsapp_examples
from bot.parser import parse_message
from engine.models import PreferenceKind


@pytest.fixture(scope="module")
def client():
    reset_state()
    get_state().today_override = date(2026, 12, 3)
    c = create_app(TestConfig).test_client()
    c.post("/generar")
    yield c
    reset_state()


@pytest.mark.parametrize(
    ("text", "avoid"),
    [
        ("No me gustan las noches", True),
        ("Quiero evitar las noches", True),
        ("Prefiero las noches", False),
        ("Prefiero no trabajar los domingos", True),
    ],
)
def test_parser_understands_negation(text, avoid):
    parsed = parse_message(text, date(2026, 12, 3))
    assert parsed.extra["avoid"] is avoid


def test_whatsapp_dislike_is_stored_as_avoid(client):
    state = get_state()
    reply(state, "EMP-003", "No me gustan las noches")
    prefs = [p for p in state.clinic.extra_preferences if p.employee_id == "EMP-003"]
    assert [p.kind for p in prefs] == [PreferenceKind.AVOID_SHIFT]
    reply(state, "EMP-003", "No me gustan las noches")
    assert len([p for p in state.clinic.extra_preferences if p.employee_id == "EMP-003"]) == 1


def test_seeded_absence_is_pending_and_not_a_legal_alert(client):
    state = get_state()
    pending = pending_absences(state, 0)
    assert len(pending) == 1 and pending[0]["options"] > 0
    assert "no puede ir" in client.get("/").get_data(as_text=True)


def test_replacement_applies_to_the_version_being_viewed(client):
    state = get_state()
    index = 1
    proposal = state.proposals[index]
    shift = next(a for a in proposal.assignments if a.day > 20)
    _, options = state.register_absence(shift.employee_id, shift.day, "Incapacidad", index)
    assert options
    before = [list(p.assignments) for p in state.proposals]
    response = client.post(
        "/novedades/reemplazar",
        data={
            "v": index,
            "employee_id": shift.employee_id,
            "day": shift.day,
            "shift_code": shift.shift_code,
            "service": shift.service,
            "replacement_id": options[0].employee_id,
        },
    )
    assert response.status_code == 302 and "v=1" in response.location
    assert proposal.at(options[0].employee_id, shift.day) is not None
    assert state.proposals[0].assignments == before[0]


def test_whatsapp_absence_shows_up_for_review(client):
    state = get_state()
    client.post("/publicar/0")
    proposal = state.proposals[0]
    today = state.clinic.day_index(state.today())
    worker = next(e.id for e in state.problem.employees if proposal.at(e.id, today + 1))
    text = reply(state, worker, "Tengo incapacidad, no puedo ir mañana")
    assert "coordinador" in text
    assert any(p["employee_id"] == worker for p in pending_absences(state, 0))


def test_every_example_message_works_for_the_suggested_person(client):
    state = get_state()
    examples, default = whatsapp_examples(state)
    assert suggestions_for(state, default) == examples[default]
    for text in examples[default]:
        answer = reply(state, default, text)
        assert "No se puede" not in answer and "No encontré" not in answer, (text, answer)
        assert "no tenías turno" not in answer, (text, answer)


@pytest.mark.parametrize(
    ("url", "data"),
    [
        ("/clinica", {"max_consecutive_nights": "", "max_consecutive_work_days": "", "max_weekly_hours": ""}),
        ("/equipo", {}),
        ("/novedades", {"employee_id": "", "day": "", "kind": ""}),
        ("/novedades/reemplazar", {}),
        ("/solicitudes/cambio", {}),
    ],
)
def test_incomplete_forms_do_not_crash(client, url, data):
    assert client.post(url, data=data).status_code == 302


def test_impossible_rule_keeps_versions_and_names_the_rule(client):
    state = get_state()
    versions = list(state.proposals)
    client.post(
        "/clinica",
        data={
            "max_consecutive_nights": 3,
            "max_consecutive_work_days": 1,
            "max_weekly_hours": 42,
            "rest_after_night": "on",
        },  # fmt: skip
    )
    response = client.post("/generar", follow_redirects=True)
    assert state.proposals == versions
    assert "Máximo de días seguidos trabajando" in response.get_data(as_text=True)
    state.clinic.policy["max_consecutive_work_days"] = 6
