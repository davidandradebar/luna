"""Estado en memoria de la demo (un solo usuario, se reinicia al reiniciar el servidor)."""

import os
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

# Personas candidatas a la novedad de ejemplo y desde qué día buscarla.
ABSENCE_SEEDS = [("EMP-009", 10), ("EMP-005", 10), ("EMP-002", 10)]


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
    today_override: date | None = None
    handled: set[str] = field(default_factory=set)
    last_error: str | None = None

    def generate(self, time_limit_s: float) -> bool:
        """Genera las versiones. Si no hay cuadro posible conserva las anteriores y explica por qué."""
        with self.lock:
            self.clinic.absences = [a for a in self.clinic.absences if not a.seed]
            problem = self.clinic.problem()
            started = time.perf_counter()
            proposals = solve_strategies(problem, STRATEGIES, time_limit_s=time_limit_s)
            if not proposals:
                self.last_error = self._diagnose()
                return False
            self.problem = problem
            self.proposals = proposals
            self.generated_in = time.perf_counter() - started
            self.selected = None
            self.status = STATUS_DRAFT
            self.log = []
            self.handled = set()
            self.last_error = None
            self._seed_absence()
            return True

    def _diagnose(self) -> str:
        """Busca qué regla de la clínica, cambiada respecto a la original, deja el cuadro imposible."""
        defaults = {k: v["value"] for k, v in self.clinic.raw["clinic_policy"].items()}
        current = dict(self.clinic.policy)
        try:
            for key, value in current.items():
                if value == defaults[key]:
                    continue
                self.clinic.policy = {**current, key: defaults[key]}
                if solve_strategies(self.clinic.problem(), STRATEGIES[:1], time_limit_s=3.0):
                    label = self.clinic.raw["clinic_policy"][key]["label"]
                    return (
                        f"La regla «{label}» en {_fmt_value(value)} deja el mes imposible de cubrir con "
                        f"el personal actual. Con {_fmt_value(defaults[key])} sí se puede."
                    )
        finally:
            self.clinic.policy = current
        return "Con las reglas y el personal actuales no existe un cuadro que cubra todos los turnos."

    def _seed_absence(self) -> None:
        """Una incapacidad de ejemplo, reportada por WhatsApp, sobre un turno que sí tiene reemplazos."""
        proposal = self.proposals[0]
        for employee_id, start in ABSENCE_SEEDS:
            for day in range(start, self.problem.days):
                shift = proposal.at(employee_id, day)
                if shift and suggest_replacements(self.problem, proposal, shift):
                    self._add_absence(Absence(employee_id, day, "Incapacidad", "WhatsApp", seed=True))
                    return

    def _add_absence(self, absence: Absence) -> None:
        self.clinic.absences.append(absence)
        if self.problem is not None:
            self.problem = self._with_absence(self.problem, absence)

    def proposal(self, index: int | None) -> RosterProposal | None:
        if not self.proposals:
            return None
        if index is None or not 0 <= index < len(self.proposals):
            index = self.selected if self.selected is not None else 0
        return self.proposals[index]

    @property
    def chosen(self) -> RosterProposal | None:
        return self.proposals[self.selected] if self.selected is not None else None

    def publish(self, index: int) -> None:
        self.selected = index
        self.status = STATUS_PUBLISHED
        self.log.append("Cuadro aprobado y publicado por el coordinador.")

    def today(self) -> date:
        if self.today_override:
            return self.today_override
        fixed = os.environ.get("LUNA_DEMO_DATE")
        if fixed:
            try:
                return date.fromisoformat(fixed)
            except ValueError:
                pass
        today = date.today()
        start = self.clinic.start
        if today.year == start.year and today.month == start.month:
            return today
        return start

    def register_absence(self, employee_id: str, day: int, kind: str, index: int | None = None, source=""):
        """Registra la novedad y devuelve (turno afectado, reemplazos sugeridos) en la versión indicada."""
        known = any(a.employee_id == employee_id and a.day == day for a in self.clinic.absences)
        if not known:
            self._add_absence(Absence(employee_id, day, kind, source or "coordinación"))
        return self.affected(employee_id, day, index)

    def affected(self, employee_id: str, day: int, index: int | None = None):
        proposal = self.proposal(index)
        if proposal is None or self.problem is None:
            return None, []
        shift = proposal.at(employee_id, day)
        if shift is None:
            return None, []
        return shift, suggest_replacements(self.problem, proposal, shift)

    def _with_absence(self, problem: RosterProblem, absence: Absence) -> RosterProblem:
        problem.unavailability = [
            *problem.unavailability,
            Unavailability(absence.employee_id, absence.day, None, absence.kind),
        ]
        return problem

    def apply_replacement(self, affected: Assignment, replacement_id: str, index: int | None = None) -> bool:
        proposal = self.proposal(index)
        current = proposal.at(affected.employee_id, affected.day) if proposal else None
        if current is None:
            return False
        proposal.assignments.remove(current)
        proposal.assignments.append(
            Assignment(replacement_id, current.day, current.shift_code, current.service)
        )
        if self.status == STATUS_PUBLISHED and proposal is self.chosen:
            self.status = STATUS_ADJUSTED
        self.log.append(
            f"{self.clinic.employee_name(replacement_id)} cubre a "
            f"{self.clinic.employee_name(affected.employee_id)} el día {affected.day + 1}."
        )
        return True


def _fmt_value(value) -> str:
    if value is True:
        return "sí"
    if value is False:
        return "no"
    return str(value)


_state = DemoState()


def get_state() -> DemoState:
    return _state


def reset_state() -> DemoState:
    global _state
    _state = DemoState()
    return _state
