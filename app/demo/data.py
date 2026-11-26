"""Construye el problema del motor a partir de los fixtures de la clínica demo."""

import calendar
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from app.rules import Rule, load_rules, resolve_rule
from engine.models import (
    CostRules,
    CoverageRequirement,
    Employee,
    Preference,
    PreferenceKind,
    RosterProblem,
    ShiftType,
    Unavailability,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
NIGHT_CODES = frozenset({"N"})
DAY_CODES = ("M", "T")
LOW_FULFILLMENT = 0.6


@dataclass
class Absence:
    employee_id: str
    day: int
    kind: str  # incapacidad, calamidad, vacaciones, permiso


@dataclass
class ClinicData:
    raw: dict
    rules: list[Rule]
    policy: dict = field(default_factory=dict)
    extra_preferences: list[Preference] = field(default_factory=list)
    absences: list[Absence] = field(default_factory=list)

    @classmethod
    def load(cls) -> "ClinicData":
        raw = json.loads((FIXTURES / "demo_clinic.json").read_text(encoding="utf-8"))
        rules = load_rules(FIXTURES / "labor_rules.json")
        policy = {k: v["value"] for k, v in raw["clinic_policy"].items()}
        return cls(raw=raw, rules=rules, policy=policy)

    # Periodo y calendario
    @property
    def start(self) -> date:
        return date(self.raw["period"]["year"], self.raw["period"]["month"], 1)

    @property
    def days(self) -> int:
        return calendar.monthrange(self.start.year, self.start.month)[1]

    @property
    def holidays(self) -> frozenset[date]:
        return frozenset(date.fromisoformat(h) for h in self.raw["holidays"])

    def day_index(self, value: date) -> int:
        return (value - self.start).days

    def date_of(self, day: int) -> date:
        return date.fromordinal(self.start.toordinal() + day)

    def is_business_day(self, day: int) -> bool:
        current = self.date_of(day)
        return current.weekday() < 5 and current not in self.holidays

    # Catálogos
    @property
    def tenant_id(self) -> str:
        return self.raw["tenant"]["id"]

    @property
    def regime(self) -> str:
        return self.raw["tenant"]["regime"]

    def role_label(self, role: str) -> str:
        return self.raw["roles"].get(role, role)

    def service_label(self, service: str) -> str:
        return next((s["name"] for s in self.raw["services"] if s["id"] == service), service)

    def raw_shift_label(self, code: str) -> str:
        return next(s["label"] for s in self.raw["shift_types"] if s["code"] == code)

    def shift_plural(self, code: str) -> str:
        """'Noche' -> 'noches', 'Mañana' -> 'mañanas'."""
        return self.raw_shift_label(code).lower() + "s"

    def employee_name(self, employee_id: str) -> str:
        return next(e["name"] for e in self.raw["employees"] if e["id"] == employee_id)

    def priority(self, employee_id: str) -> float:
        record = self.raw.get("history", {}).get(employee_id)
        if not record or record["last_month_fulfilled"] >= LOW_FULFILLMENT:
            return 0.0
        return round(1 - record["last_month_fulfilled"], 2)

    def rule(self, key: str) -> Rule:
        return resolve_rule(self.rules, key, self.regime, self.start, tenant_id=self.tenant_id)

    def legal_max_weekly_hours(self) -> int:
        return int(self.rule("max_weekly_hours").value)

    def cost_rules(self) -> CostRules:
        return CostRules(
            monthly_hours_divisor=int(self.rule("monthly_ordinary_hours_divisor").value),
            night_start=int(self.rule("night_shift_start").value),
            day_start=int(self.rule("day_shift_start").value),
            night_surcharge=float(self.rule("night_surcharge").value),
            sunday_holiday_surcharge=float(self.rule("sunday_holiday_surcharge").value),
        )

    # Construcción del problema
    def employees(self) -> list[Employee]:
        return [
            Employee(
                id=e["id"],
                role=e["role"],
                competencies=frozenset(e["competencies"]),
                name=e["name"],
                monthly_salary=e["monthly_salary"],
                priority=self.priority(e["id"]),
                min_hours=e.get("min_monthly_hours"),
            )
            for e in self.raw["employees"]
        ]

    def coverage(self) -> list[CoverageRequirement]:
        result = []
        for item in self.raw["coverage"]:
            for d in range(self.days):
                if item["days"] == "business" and not self.is_business_day(d):
                    continue
                for code, minimum in item["shifts"].items():
                    result.append(CoverageRequirement(item["service"], d, code, item["role"], minimum))
        return result

    def unavailability(self) -> list[Unavailability]:
        result = []
        for item in self.raw["availability"]:
            for d in range(self.days):
                if item["weekday"] is None or self.date_of(d).weekday() == item["weekday"]:
                    result.append(Unavailability(item["employee_id"], d, item["shift_code"], item["note"]))
        for a in self.absences:
            result.append(Unavailability(a.employee_id, a.day, None, a.kind))
        return result

    def preferences(self) -> list[Preference]:
        result = []
        for item in self.raw["preferences"]:
            kind = PreferenceKind(item["kind"])
            value = item["value"]
            if kind == PreferenceKind.DAY_OFF:
                value = self.day_index(date.fromisoformat(value))
            result.append(Preference(item["employee_id"], kind, value, item["weight"], item["note"]))
        return result + self.extra_preferences

    def problem(self) -> RosterProblem:
        legal_max = self.legal_max_weekly_hours()
        forbidden = [("N", c) for c in DAY_CODES] if self.policy["rest_after_night"] else []
        return RosterProblem(
            days=self.days,
            employees=self.employees(),
            shift_types=[ShiftType(**s) for s in self.raw["shift_types"]],
            coverage=self.coverage(),
            unavailability=self.unavailability(),
            preferences=self.preferences(),
            start_date=self.start,
            holidays=self.holidays,
            max_weekly_hours=min(int(self.policy["max_weekly_hours"]), legal_max),
            max_consecutive_nights=int(self.policy["max_consecutive_nights"]),
            max_consecutive_work_days=int(self.policy["max_consecutive_work_days"]),
            night_shift_codes=NIGHT_CODES,
            forbidden_sequences=forbidden,
            cost_rules=self.cost_rules(),
        )
