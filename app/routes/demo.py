"""Rutas de la demo guiada."""

import math
from datetime import date
from io import BytesIO

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from app.demo.export import build_workbook
from app.demo.requests import absence_request, swap_requests
from app.demo.state import get_state, reset_state
from app.demo.whatsapp import reply
from engine.checks import apply_swap, check_swap, legal_alerts
from engine.cost import roster_cost
from engine.explain import explain
from engine.metrics import coverage_gaps, fairness, preference_rate, preference_results
from engine.models import Assignment, Preference, PreferenceKind

bp = Blueprint("demo", __name__)

WEEKDAY_SHORT = ["L", "M", "X", "J", "V", "S", "D"]
WEEKDAY_NAMES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
ABSENCE_KINDS = ["Incapacidad", "Calamidad doméstica", "Licencia", "Permiso"]
WHATSAPP_SUGGESTIONS = [
    "¿Qué turno tengo el viernes?",
    "¿Cuántas horas llevo?",
    "Necesito libre el 20",
    "Prefiero las noches",
    "Quiero cambiar mi turno del 12 con Carlos",
    "Tengo incapacidad, no puedo ir mañana",
]


@bp.app_template_filter("cop")
def cop(value: float) -> str:
    return "$" + f"{round(value):,}".replace(",", ".")


@bp.app_context_processor
def inject_globals():
    state = get_state()
    return {
        "clinic": state.clinic,
        "state": state,
        "weekday_short": WEEKDAY_SHORT,
        "weekday_names": WEEKDAY_NAMES,
        "static_export": current_app.config.get("STATIC_EXPORT", False),
    }


def _summary(index: int) -> dict:
    state = get_state()
    proposal = state.proposals[index]
    problem = state.problem
    results = preference_results(problem, proposal)
    return {
        "index": index,
        "proposal": proposal,
        "cost": roster_cost(problem, proposal),
        "pref_rate": preference_rate(results),
        "pref_results": results,
        "unmet": [r for r in results if not r.fulfilled],
        "fairness": [f for f in fairness(problem, proposal) if f.nights_max or f.holidays_max],
        "gaps": coverage_gaps(problem, proposal),
        "alerts": legal_alerts(problem, proposal),
    }


def _grid(index: int) -> dict:
    state = get_state()
    problem = state.problem
    proposal = state.proposals[index]
    days = [
        {
            "index": d,
            "number": d + 1,
            "weekday": problem.weekday_of(d),
            "holiday": problem.is_sunday_or_holiday(d),
        }
        for d in range(problem.days)
    ]
    rows = []
    for e in problem.employees:
        mine = proposal.for_employee(e.id)
        rows.append(
            {
                "employee": e,
                "services": sorted({a.service for a in mine}),
                "hours": sum(problem.shift(a.shift_code).hours for a in mine),
            }
        )
    return {
        "grid": {(a.employee_id, a.day): a for a in proposal.assignments},
        "rows": rows,
        "days": days,
        "absences": {(u.employee_id, u.day) for u in problem.unavailability if u.shift_code is None},
    }


DEMO_HOUR = 9  # hora de referencia del tablero: la reunión es a las 9 a. m.
ROLE_SHORT = {
    "psiquiatra": "Psiquiatría",
    "enfermera_jefe": "Jefe",
    "auxiliar_enfermeria": "Auxiliar",
    "psicologo": "Psicología",
    "terapeuta_ocupacional": "T. ocupacional",
}


def _arc(start: float, end: float, radius: float = 46, center: float = 60) -> str:
    """Arco SVG de un reloj de 24 horas: el mediodía arriba y la medianoche abajo."""
    span = (end - start) % 24 or 24
    start, end = start + 0.12, start + span - 0.12

    def point(hour: float) -> str:
        angle = (hour - 12) / 24 * 2 * math.pi - math.pi / 2
        return f"{center + radius * math.cos(angle):.2f} {center + radius * math.sin(angle):.2f}"

    large = 1 if span > 12 else 0
    return f"M {point(start)} A {radius} {radius} 0 {large} 1 {point(end)}"


def _hand(hour: float, radius: float = 34, center: float = 60) -> dict:
    angle = (hour - 12) / 24 * 2 * math.pi - math.pi / 2
    x, y = center + radius * math.cos(angle), center + radius * math.sin(angle)
    return {"x": round(x, 2), "y": round(y, 2)}


def _hour_of(text: str) -> int:
    return int(text.split(":")[0])


def _pulse(index: int) -> dict:
    """Datos del tablero de 24 horas: quién está en cada servicio y turno, día por día."""
    state = get_state()
    clinic = state.clinic
    problem = state.problem
    proposal = state.proposals[index]
    shifts = clinic.raw["shift_types"]
    services = clinic.raw["services"]
    need: dict[tuple, int] = {}
    for c in problem.coverage:
        key = (c.day, c.service, c.shift_code)
        need[key] = need.get(key, 0) + c.minimum
    people: dict[tuple, list] = {}
    for a in sorted(proposal.assignments, key=lambda a: a.employee_id):
        e = problem.employee(a.employee_id)
        people.setdefault((a.day, a.service, a.shift_code), []).append(
            {"name": e.display_name, "role": ROLE_SHORT.get(e.role, e.role), "role_key": e.role}
        )
    days = []
    for d in range(problem.days):
        days.append(
            {
                "index": d,
                "label": f"{WEEKDAY_NAMES[problem.weekday_of(d)]} {d + 1}",
                "short": WEEKDAY_SHORT[problem.weekday_of(d)],
                "holiday": problem.is_sunday_or_holiday(d),
                "services": {
                    s["id"]: {
                        t["code"]: {
                            "people": people.get((d, s["id"], t["code"]), []),
                            "need": need.get((d, s["id"], t["code"]), 0),
                        }
                        for t in shifts
                    }
                    for s in services
                },
            }
        )
    today = (state.today() - clinic.start).days
    today = today if 0 <= today < problem.days else 0
    now_shift = next(
        t["code"]
        for t in shifts
        if (_hour_of(t["start"]) <= DEMO_HOUR < _hour_of(t["end"]))
        or (t["crosses_midnight"] and (DEMO_HOUR >= _hour_of(t["start"]) or DEMO_HOUR < _hour_of(t["end"])))
    )
    return {
        "pulse_days": days,
        "today": today,
        "now_shift": now_shift,
        "demo_hour": DEMO_HOUR,
        "arcs": {t["code"]: _arc(_hour_of(t["start"]), _hour_of(t["end"])) for t in shifts},
        "hand": _hand(DEMO_HOUR),
        "service_names": {s["id"]: s["name"].replace("Hospitalización ", "").capitalize() for s in services},
    }


def _require_proposals():
    if not get_state().proposals:
        flash("Primero genere los cuadros.")
        return redirect(url_for("demo.generate"))
    return None


@bp.get("/")
def home():
    state = get_state()
    problem = state.problem or state.clinic.problem()
    context = {
        "slots": sum(c.minimum for c in problem.coverage),
        "people": len(problem.employees),
        "preferences": len(problem.preferences),
    }
    if state.proposals:
        default = state.selected if state.selected is not None else 0
        index = request.args.get("v", default, type=int)
        if not 0 <= index < len(state.proposals):
            index = 0
        context |= {"summary": _summary(index), **_grid(index)}
        context["versions"] = [_summary(i) for i in range(len(state.proposals))]
        context["swaps"] = swap_requests(state, index)
        context["pending_absence"] = absence_request(state, index)
        context |= _pulse(index)
    return render_template("demo/home.html", **context)


@bp.route("/clinica", methods=["GET", "POST"])
def clinic():
    state = get_state()
    data = state.clinic
    if request.method == "POST":
        legal_max = data.legal_max_weekly_hours()
        weekly = int(request.form.get("max_weekly_hours", legal_max))
        data.policy.update(
            max_consecutive_nights=int(request.form["max_consecutive_nights"]),
            max_consecutive_work_days=int(request.form["max_consecutive_work_days"]),
            rest_after_night="rest_after_night" in request.form,
            max_weekly_hours=min(weekly, legal_max),
        )
        if weekly > legal_max:
            flash(f"La clínica no puede superar el máximo legal de {legal_max} horas semanales.")
        flash("Reglas guardadas. Genere el cuadro de nuevo para aplicarlas.")
        return redirect(url_for("demo.clinic"))

    coverage = {}
    for item in data.raw["coverage"]:
        svc = coverage.setdefault(item["service"], [])
        svc.append(item)
    legal = [
        ("Jornada máxima semanal", data.rule("max_weekly_hours"), "h"),
        ("Divisor de hora ordinaria", data.rule("monthly_ordinary_hours_divisor"), "h/mes"),
        ("Inicio jornada nocturna", data.rule("night_shift_start"), ":00"),
        ("Recargo nocturno", data.rule("night_surcharge"), "%"),
        ("Recargo dominical y festivo", data.rule("sunday_holiday_surcharge"), "%"),
    ]
    return render_template(
        "demo/clinic.html", coverage=coverage, legal=legal, policy=data.raw["clinic_policy"], step=1
    )


@bp.route("/equipo", methods=["GET", "POST"])
def team():
    state = get_state()
    data = state.clinic
    if request.method == "POST":
        employee_id = request.form["employee_id"]
        kind = PreferenceKind(request.form["kind"])
        if kind == PreferenceKind.DAY_OFF:
            day = data.day_index(date.fromisoformat(request.form["day"]))
            pref = Preference(employee_id, kind, day, 3, f"Libre el {day + 1}")
        elif kind == PreferenceKind.PREFER_SHIFT:
            code = request.form["shift_code"]
            pref = Preference(employee_id, kind, code, 2, f"Prefiere {data.shift_plural(code)}")
        else:
            wd = int(request.form["weekday"])
            pref = Preference(employee_id, kind, wd, 2, f"Evitar {WEEKDAY_NAMES[wd].lower()}s")
        data.extra_preferences.append(pref)
        flash(f"Preferencia agregada a {data.employee_name(employee_id)}.")
        return redirect(url_for("demo.team"))

    prefs: dict[str, list[Preference]] = {}
    for p in data.preferences():
        prefs.setdefault(p.employee_id, []).append(p)
    availability: dict[str, list[str]] = {}
    for a in data.raw["availability"]:
        availability.setdefault(a["employee_id"], []).append(a["note"])
    groups: dict[str, list[dict]] = {}
    for e in data.raw["employees"]:
        groups.setdefault(e["role"], []).append(e)
    return render_template("demo/team.html", groups=groups, prefs=prefs, availability=availability, step=2)


@bp.route("/generar", methods=["GET", "POST"])
def generate():
    state = get_state()
    if request.method == "POST":
        state.generate(current_app.config.get("DEMO_TIME_LIMIT", 6.0))
        if not state.proposals:
            flash("Con las reglas actuales no existe un cuadro posible. Revise reglas o personal.")
            return redirect(url_for("demo.generate"))
        return redirect(url_for("demo.home"))
    problem = state.clinic.problem()
    return render_template(
        "demo/generate.html",
        slots=sum(c.minimum for c in problem.coverage),
        problem=problem,
        step=3,
    )


@bp.get("/comparar")
def compare():
    if (r := _require_proposals()) is not None:
        return r
    summaries = [_summary(i) for i in range(len(get_state().proposals))]
    cheapest = min(s["cost"].total for s in summaries)
    return render_template("demo/compare.html", summaries=summaries, cheapest=cheapest, step=4)


@bp.get("/cuadro/<int:index>")
def roster(index: int):
    if (r := _require_proposals()) is not None:
        return r
    state = get_state()
    if index >= len(state.proposals):
        abort(404)
    service = request.args.get("servicio", "todos")
    problem = state.problem
    proposal = state.proposals[index]
    grid = {(a.employee_id, a.day): a for a in proposal.assignments}
    services = state.clinic.raw["services"]
    employees = [
        e
        for e in problem.employees
        if service == "todos" or any(a.service == service for a in proposal.for_employee(e.id))
    ]
    days = [
        {
            "index": d,
            "number": d + 1,
            "weekday": problem.weekday_of(d),
            "holiday": problem.is_sunday_or_holiday(d),
        }
        for d in range(problem.days)
    ]
    absences = {(u.employee_id, u.day) for u in problem.unavailability if u.shift_code is None}
    return render_template(
        "demo/roster.html",
        summary=_summary(index),
        grid=grid,
        employees=employees,
        days=days,
        services=services,
        service=service,
        absences=absences,
        step=4,
    )


@bp.get("/api/explicar/<int:index>/<employee_id>/<int:day>")
def explain_api(index: int, employee_id: str, day: int):
    state = get_state()
    if index >= len(state.proposals):
        abort(404)
    result = explain(state.problem, state.proposals[index], employee_id, day)
    result["date"] = f"{WEEKDAY_NAMES[state.problem.weekday_of(day)]} {day + 1}"
    return jsonify(result)


@bp.post("/publicar/<int:index>")
def publish(index: int):
    if (r := _require_proposals()) is not None:
        return r
    get_state().publish(index)
    return redirect(url_for("demo.published"))


@bp.get("/publicado")
def published():
    state = get_state()
    if state.chosen is None:
        return redirect(url_for("demo.compare"))
    notices, seen_roles = [], set()
    for e in state.problem.employees:
        if e.role in seen_roles:
            continue
        seen_roles.add(e.role)
        notices.append({"employee": e, "shifts": state.chosen.for_employee(e.id)[:3]})
    return render_template("demo/published.html", notices=notices[:4])


@bp.route("/novedades", methods=["GET", "POST"])
def absences():
    if (r := _require_proposals()) is not None:
        return r
    state = get_state()
    affected, options = None, []
    if request.method == "POST":
        employee_id = request.form["employee_id"]
        day = int(request.form["day"]) - 1
        affected, options = state.register_absence(employee_id, day, request.form["kind"])
        if request.form.get("key"):
            state.handled.add(request.form["key"])
        if affected is None:
            flash("Novedad registrada. Esa persona no tenía turno ese día; no hay que reemplazar.")
    return render_template(
        "demo/absences.html",
        affected=affected,
        options=options,
        kinds=ABSENCE_KINDS,
        prefill_emp=request.args.get("emp", ""),
        prefill_day=request.args.get("dia", type=int) or state.today().day,
        prefill_key=request.args.get("clave", ""),
    )


@bp.post("/novedades/reemplazar")
def apply_replacement():
    state = get_state()
    affected = Assignment(
        request.form["employee_id"],
        int(request.form["day"]),
        request.form["shift_code"],
        request.form["service"],
    )
    state.apply_replacement(affected, request.form["replacement_id"])
    flash("Reemplazo aplicado. El cuadro quedó ajustado y se notificó por WhatsApp (simulado).")
    index = state.selected if state.selected is not None else 0
    return redirect(url_for("demo.home", v=index))


@bp.post("/solicitudes/cambio")
def approve_swap():
    state = get_state()
    index = int(request.form["index"])
    requester, other, day = request.form["requester"], request.form["other"], int(request.form["day"])
    check = check_swap(state.problem, state.proposals[index], requester, other, day)
    if check.valid:
        apply_swap(check, other)
        state.handled.add(request.form["key"])
        state.log.append(
            f"Cambio aprobado: {state.clinic.employee_name(other)} cubre a "
            f"{state.clinic.employee_name(requester)} el día {day + 1}."
        )
        flash("Cambio aprobado. Ambos reciben la confirmación por WhatsApp (simulado).")
    else:
        flash("El cambio ya no es válido con el cuadro actual.")
    return redirect(url_for("demo.home", v=index))


@bp.get("/whatsapp")
def whatsapp():
    return render_template("demo/whatsapp.html", step=7, suggestions=WHATSAPP_SUGGESTIONS)


@bp.post("/api/whatsapp")
def whatsapp_api():
    payload = request.get_json(force=True)
    return jsonify(reply=reply(get_state(), payload["employee_id"], payload["text"]))


@bp.get("/exportar/<int:index>")
def export(index: int):
    state = get_state()
    if index >= len(state.proposals):
        abort(404)
    content = build_workbook(state.clinic, state.problem, state.proposals[index])
    return send_file(
        BytesIO(content),
        as_attachment=True,
        download_name=f"cuadro_{state.proposals[index].strategy.key}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.post("/reiniciar")
def restart():
    reset_state()
    flash("Demo reiniciada.")
    return redirect(url_for("demo.home"))
