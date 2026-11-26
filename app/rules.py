"""Resolución de reglas laborales vigentes.

Prioridad: regla del tenant sobre regla global; dentro de cada nivel, la de
vigencia más reciente que cubra la fecha consultada.
"""

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path


class RuleNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class Rule:
    key: str
    regime: str
    value: Decimal
    unit: str
    valid_from: date
    valid_to: date | None
    source: str
    verification_status: str
    tenant_id: str | None = None

    def is_active(self, on: date) -> bool:
        return self.valid_from <= on and (self.valid_to is None or on <= self.valid_to)


def resolve_rule(rules: list[Rule], key: str, regime: str, on: date, tenant_id: str | None = None) -> Rule:
    candidates = [r for r in rules if r.key == key and r.regime == regime and r.is_active(on)]
    scopes = [tenant_id, None] if tenant_id else [None]
    for scope in scopes:
        scoped = [r for r in candidates if r.tenant_id == scope]
        if scoped:
            return max(scoped, key=lambda r: r.valid_from)
    raise RuleNotFoundError(f"Sin regla vigente: {key} / {regime} / {on.isoformat()}")


def load_rules(path: Path) -> list[Rule]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        Rule(
            key=item["key"],
            regime=item["regime"],
            value=Decimal(str(item["value"])),
            unit=item["unit"],
            valid_from=date.fromisoformat(item["valid_from"]),
            valid_to=date.fromisoformat(item["valid_to"]) if item.get("valid_to") else None,
            source=item["source"],
            verification_status=item["verification_status"],
            tenant_id=item.get("tenant_id"),
        )
        for item in raw["rules"]
    ]
