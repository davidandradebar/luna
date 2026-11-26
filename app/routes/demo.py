"""Rutas de la demo guiada."""

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
from app.demo.state import get_state, reset_state
from app.demo.whatsapp import reply
from engine.checks import legal_alerts
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
    sample = state.problem.employees[0]
    first = state.chosen.for_employee(sample.id)[:3]
    return render_template("demo/published.html", sample=sample, first=first, step=5)


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
        if affected is None:
            flash("Novedad registrada. Esa persona no tenía turno ese día; no hay que reemplazar.")
    return render_template(
        "demo/absences.html",
        affected=affected,
        options=options,
        kinds=ABSENCE_KINDS,
        step=6,
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
