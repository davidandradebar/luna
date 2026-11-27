"""Solicitudes pendientes de ejemplo para la bandeja del coordinador."""

from dataclasses import dataclass

from app.demo.state import DemoState
from engine.checks import SwapCheck, check_swap

# Solicitudes ficticias que llegaron por WhatsApp: quién pide, con quién y desde qué día.
SWAP_SEEDS = [("EMP-006", "auxiliar_enfermeria", 9), ("EMP-014", "enfermera_jefe", 16)]
ABSENCE_SEED = ("EMP-009", 10)


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


def absence_request(state: DemoState, index: int):
    employee_id, start = ABSENCE_SEED
    proposal = state.proposals[index]
    for day in range(start, state.problem.days):
        if proposal.at(employee_id, day) and f"absence-{employee_id}" not in state.handled:
            return {"key": f"absence-{employee_id}", "employee_id": employee_id, "day": day}
    return None
