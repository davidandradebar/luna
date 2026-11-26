"""Trabajos en segundo plano (RQ)."""

from engine.models import RosterProblem
from engine.solver import solve


def generate_roster(problem: RosterProblem, max_solutions: int = 3) -> list[dict]:
    """Genera propuestas de cuadro. El coordinador escoge; nunca se publica solo."""
    return [proposal.to_dict() for proposal in solve(problem, max_solutions=max_solutions)]
