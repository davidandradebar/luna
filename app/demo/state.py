"""Estado en memoria de la demo (un solo usuario, se reinicia al reiniciar el servidor)."""

import threading
import time
from dataclasses import dataclass, field
from datetime import date

from app.demo.data import Absence, ClinicData
from engine.checks import suggest_replacements
from engine.models import Assignment, RosterProblem, RosterProposal, Unavailability
from engine.solver import STRATEGIES, solve_strategies

STATUS_DRAFT = "borrador"
STATUS_PUBLISHED = "publicado"
STATUS_ADJUSTED = "ajustado"


@dataclass
class DemoState:
    clinic: ClinicData = field(default_factory=ClinicData.load)
    problem: RosterProblem | None = None
    proposals: list[RosterProposal] = field(default_factory=list)
    selected: int | None = None
    status: str = STATUS_DRAFT
    generated_in: float = 0.0
    log: list[str] = field(default_factory=list)
    chats: dict[str, list[dict]] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def generate(self, time_limit_s: float) -> None:
        with self.lock:
            problem = self.clinic.problem()
            started = time.perf_counter()
            proposals = solve_strategies(problem, STRATEGIES, time_limit_s=time_limit_s)
            self.problem = problem
            self.proposals = proposals
            self.generated_in = time.perf_counter() - started
            self.selected = None
            self.status = STATUS_DRAFT
            self.log = []

    @property
    def chosen(self) -> RosterProposal | None:
        return self.proposals[self.selected] if self.selected is not None else None

    def publish(self, index: int) -> None:
        self.selected = index
        self.status = STATUS_PUBLISHED
        self.log.append("Cuadro aprobado y publicado por el coordinador.")

    def today(self) -> date:
        today = date.today()
        start = self.clinic.start
        if today.year == start.year and today.month == start.month:
            return today
        return start

    def register_absence(self, employee_id: str, day: int, kind: str):
        """Registra la novedad y devuelve (turno afectado, reemplazos sugeridos)."""
        absence = Absence(employee_id, day, kind)
        self.clinic.absences.append(absence)
        if self.problem is not None:
            self.problem = self._with_absence(self.problem, absence)
        proposal = self.chosen or (self.proposals[0] if self.proposals else None)
        if proposal is None or self.problem is None:
            return None, []
        affected = proposal.at(employee_id, day)
        if affected is None:
            return None, []
        return affected, suggest_replacements(self.problem, proposal, affected)

    def _with_absence(self, problem: RosterProblem, absence: Absence) -> RosterProblem:
        problem.unavailability = [
            *problem.unavailability,
            Unavailability(absence.employee_id, absence.day, None, absence.kind),
        ]
        return problem

    def apply_replacement(self, affected: Assignment, replacement_id: str) -> None:
        proposal = self.chosen or self.proposals[0]
        current = proposal.at(affected.employee_id, affected.day)
        if current is None:
            return
        proposal.assignments.remove(current)
        proposal.assignments.append(
            Assignment(replacement_id, current.day, current.shift_code, current.service)
        )
        if self.status == STATUS_PUBLISHED:
            self.status = STATUS_ADJUSTED
        self.log.append(
            f"{self.clinic.employee_name(affected.employee_id)} reemplazado(a) por "
            f"{self.clinic.employee_name(replacement_id)} el día {affected.day + 1}."
        )


_state = DemoState()


def get_state() -> DemoState:
    return _state


def reset_state() -> DemoState:
    global _state
    _state = DemoState()
    return _state
