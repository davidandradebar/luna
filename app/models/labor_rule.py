"""Tabla de reglas laborales parametrizadas.

Ningún valor legal se quema en el código: cada regla vive aquí, por tenant
(o global cuando tenant_id es nulo) y por régimen, con vigencia por fecha.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LaborRule(Base):
    __tablename__ = "labor_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), index=True)
    regime: Mapped[str] = mapped_column(String(32))
    key: Mapped[str] = mapped_column(String(64))
    value: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    unit: Mapped[str] = mapped_column(String(16))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(255))
    verification_status: Mapped[str] = mapped_column(String(16), default="por_verificar")
