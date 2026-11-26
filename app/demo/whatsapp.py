"""Simulación del canal de WhatsApp para la demo."""

from app.demo.state import DemoState
from bot.intents import Intent
from bot.parser import parse_message
from engine.checks import blocking_reasons, suggest_replacements
from engine.cost import classify_hours
from engine.models import Preference, PreferenceKind

WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]  # fmt: skip

HELP = (
    "Puedo ayudarte con:\n"
    "• ¿Qué turno tengo el viernes?\n"
    "• ¿Cuántas horas llevo?\n"
    "• Necesito libre el 20\n"
    "• Prefiero las noches\n"
    "• Quiero cambiar mi turno del 12 con Laura\n"
    "• Tengo incapacidad, no puedo ir hoy"
)


def _fmt(state: DemoState, day: int) -> str:
    d = state.clinic.date_of(day)
    return f"{WEEKDAYS[d.weekday()]} {d.day} de {MONTHS[d.month - 1]}"


def reply(state: DemoState, employee_id: str, text: str) -> str:
    clinic = state.clinic
    names = [e["name"] for e in clinic.raw["employees"] if e["id"] != employee_id]
    parsed = parse_message(text, state.today(), names)
    proposal = state.chosen
    problem = state.problem
    first_name = clinic.employee_name(employee_id).split()[0]

    if parsed.intent is None:
        return f"Hola {first_name}, soy LUNA. {HELP}"

    day = clinic.day_index(parsed.day) if parsed.day else None
    if day is not None and not 0 <= day < clinic.days:
        return "Ese día está fuera del cuadro de este mes."

    if parsed.intent == Intent.REQUEST_DAY_OFF:
        clinic.extra_preferences.append(
            Preference(employee_id, PreferenceKind.DAY_OFF, day, 3, f"Libre el {day + 1} (por WhatsApp)")
        )
        return (
            f"Listo {first_name}, registré tu petición de libre para el {_fmt(state, day)}. "
            "La tendré en cuenta al generar el próximo cuadro."
        )

    if parsed.intent == Intent.REGISTER_PREFERENCE:
        if parsed.shift_code:
            value, label = parsed.shift_code, clinic.shift_plural(parsed.shift_code)
            kind, note = PreferenceKind.PREFER_SHIFT, f"Prefiere {label} (por WhatsApp)"
        else:
            value, kind = parsed.weekday, PreferenceKind.AVOID_WEEKDAY
            note = f"Evitar {WEEKDAYS[parsed.weekday]} (por WhatsApp)"
        clinic.extra_preferences.append(Preference(employee_id, kind, value, 2, note))
        return f"Anotado: {note.split(' (')[0].lower()}. Es una preferencia, no una garantía."

    if proposal is None or problem is None:
        return "El cuadro de este mes todavía no está publicado. Te aviso apenas salga."

    if parsed.intent == Intent.QUERY_SHIFT:
        a = proposal.at(employee_id, day)
        if a is None:
            return f"El {_fmt(state, day)} estás libre."
        shift = problem.shift(a.shift_code)
        return (
            f"El {_fmt(state, day)} tienes turno de {shift.label.lower()} ({shift.start} a {shift.end}) "
            f"en {clinic.service_label(a.service)}."
        )

    if parsed.intent == Intent.QUERY_HOURS:
        mine = proposal.for_employee(employee_id)
        hours = [classify_hours(problem, a) for a in mine]
        total = sum(h.total for h in hours)
        night = sum(h.ordinary_night + h.holiday_night for h in hours)
        holiday = sum(h.holiday_day + h.holiday_night for h in hours)
        return (
            f"Este mes tienes {len(mine)} turnos y {total} horas: {night} nocturnas y "
            f"{holiday} en domingo o festivo."
        )

    if parsed.intent == Intent.REPORT_ABSENCE:
        affected, options = state.register_absence(employee_id, day, "Incapacidad (reportada por WhatsApp)")
        if affected is None:
            return f"Registré tu novedad para el {_fmt(state, day)}. Ese día no tenías turno."
        names = ", ".join(clinic.employee_name(o.employee_id) for o in options[:3]) or "nadie disponible"
        return (
            f"Registré tu novedad para el {_fmt(state, day)}. Ya avisé a tu coordinador con "
            f"opciones de reemplazo ({names}). ¡Que te mejores!"
        )

    if parsed.intent == Intent.REQUEST_SWAP:
        if parsed.other_name is None:
            return "¿Con quién quieres cambiar? Escríbeme su nombre."
        mine = proposal.at(employee_id, day) if day is not None else None
        if mine is None:
            return "No encontré un turno tuyo ese día. ¿Qué día quieres cambiar?"
        other = next(e["id"] for e in clinic.raw["employees"] if e["name"] == parsed.other_name)
        if problem.employee(other).role != problem.employee(employee_id).role:
            return f"{parsed.other_name} tiene otro cargo, no puede cubrir tu turno."
        theirs = proposal.at(other, mine.day)
        if theirs and theirs.shift_code == mine.shift_code and theirs.service == mine.service:
            return f"{parsed.other_name} tiene el mismo turno ese día; no hay nada que cambiar."
        reasons = blocking_reasons(
            problem, proposal, other, mine.day, mine.shift_code, mine.service, ignore=theirs
        )
        if theirs and not reasons:
            reasons = [
                f"tú no puedes tomar el suyo: {r.lower()}"
                for r in blocking_reasons(
                    problem, proposal, employee_id, theirs.day, theirs.shift_code, theirs.service, ignore=mine
                )
            ]
        if reasons:
            reason = reasons[0][0].lower() + reasons[0][1:]
            options = suggest_replacements(problem, proposal, mine, limit=3)
            alt = ", ".join(clinic.employee_name(o.employee_id) for o in options)
            hint = f" Quienes sí pueden tomarlo: {alt}." if alt else ""
            return f"No se puede con {parsed.other_name}: {reason}.{hint}"
        trade = (
            f"tú tomas su {problem.shift(theirs.shift_code).label.lower()} y {parsed.other_name} tu "
            f"{problem.shift(mine.shift_code).label.lower()}"
            if theirs
            else f"{parsed.other_name} toma tu turno"
        )
        return (
            f"Validado para el {_fmt(state, day)}: {trade}, sin romper ninguna regla ni dejar el "
            "servicio descubierto. Le pregunté si acepta; después tu jefe lo aprueba con un clic."
        )

    return HELP
