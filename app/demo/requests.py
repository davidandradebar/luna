"""Solicitudes pendientes de ejemplo para la bandeja del coordinador."""

from dataclasses import dataclass

from app.demo.state import DemoState
from engine.checks import SwapCheck, check_swap, suggest_replacements

# Solicitudes ficticias que llegaron por WhatsApp: quién pide, con quién y desde qué día.
SWAP_SEEDS = [("EMP-006", "auxiliar_enfermeria", 9), ("EMP-014", "enfermera_jefe", 16)]


@dataclass
class SwapRequest:
    key: str
    requester: str
    other: str
    day: int
    check: SwapCheck


def swap_requests(state: DemoState, index: int) -> list[SwapRequest]:
    """Una solicitud válida y una que LUNA rechaza, para mostrar ambos casos."""
    problem, proposal = state.problem, state.proposals[index]
    result = []
    for n, (requester, role, start) in enumerate(SWAP_SEEDS):
        want_valid = n == 0
        peers = [e.id for e in problem.employees if e.role == role and e.id != requester]
        found = None
        for day in range(start, problem.days):
            if proposal.at(requester, day) is None:
                continue
            for other in peers:
                check = check_swap(problem, proposal, requester, other, day)
                simple = check.theirs is None  # la otra persona está libre: cubre el turno
                if check.valid == want_valid and check.mine is not None and simple:
                    found = SwapRequest(f"swap-{requester}", requester, other, day, check)
                    break
            if found:
                break
        if found and found.key not in state.handled:
            result.append(found)
    return result


def pending_absences(state: DemoState, index: int) -> list[dict]:
    """Novedades registradas cuya persona sigue asignada ese día en la versión que se ve."""
    problem, proposal = state.problem, state.proposals[index]
    result = []
    for a in sorted(state.clinic.absences, key=lambda a: a.day):
        shift = proposal.at(a.employee_id, a.day)
        if shift is None:
            continue
        options = suggest_replacements(problem, proposal, shift)
        result.append(
            {
                "employee_id": a.employee_id,
                "day": a.day,
                "kind": a.kind,
                "source": a.source,
                "shift": shift,
                "options": len(options),
            }  # fmt: skip
        )
    return result


def pending_keys(state: DemoState, index: int) -> set[tuple[str, int]]:
    return {(p["employee_id"], p["day"]) for p in pending_absences(state, index)}
