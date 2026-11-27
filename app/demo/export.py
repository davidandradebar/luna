"""Exportación del cuadro a Excel (cuadro, horas para nómina y resumen)."""

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.demo.data import ClinicData
from engine.cost import roster_cost
from engine.metrics import preference_rate, preference_results
from engine.models import RosterProblem, RosterProposal

FILLS = {
    "M": PatternFill("solid", fgColor="FFF3C4"),
    "T": PatternFill("solid", fgColor="CDE8F6"),
    "N": PatternFill("solid", fgColor="D9D2F5"),
}
WEEKDAY_SHORT = ["L", "M", "X", "J", "V", "S", "D"]
BOLD = Font(bold=True)


def build_workbook(clinic: ClinicData, problem: RosterProblem, proposal: RosterProposal) -> bytes:
    wb = Workbook()
    grid = wb.active
    grid.title = "Cuadro"
    grid.append(["Nombre", "Cargo", *[f"{d + 1}" for d in range(problem.days)], "Horas"])
    grid.append(["", "", *[WEEKDAY_SHORT[problem.weekday_of(d)] for d in range(problem.days)], ""])
    for cell in grid[1] + grid[2]:
        cell.font = BOLD
        cell.alignment = Alignment(horizontal="center")
    for emp in problem.employees:
        row = [emp.display_name, clinic.role_label(emp.role)]
        hours = 0
        for d in range(problem.days):
            a = proposal.at(emp.id, d)
            row.append(a.shift_code if a else "")
            hours += problem.shift(a.shift_code).hours if a else 0
        grid.append([*row, hours])
        for d in range(problem.days):
            cell = grid.cell(row=grid.max_row, column=3 + d)
            cell.alignment = Alignment(horizontal="center")
            if cell.value in FILLS:
                cell.fill = FILLS[cell.value]
    grid.column_dimensions["A"].width = 20
    grid.column_dimensions["B"].width = 24
    for d in range(problem.days):
        grid.column_dimensions[get_column_letter(3 + d)].width = 4
    grid.freeze_panes = "C3"

    cost = roster_cost(problem, proposal)
    payroll = wb.create_sheet("Horas para nómina")
    payroll.append(
        [
            "Nombre",
            "Cargo",
            "Ordinarias diurnas",
            "Nocturnas",
            "Dominical/festiva diurna",
            "Dominical/festiva nocturna",
            "Total horas",
            "Recargos estimados",
        ]
    )
    for cell in payroll[1]:
        cell.font = BOLD
    for emp in problem.employees:
        item = cost.by_employee.get(emp.id)
        if item is None:
            continue
        h = item.hours
        payroll.append(
            [
                emp.display_name,
                clinic.role_label(emp.role),
                h.ordinary_day,
                h.ordinary_night,
                h.holiday_day,
                h.holiday_night,
                h.total,
                round(item.surcharges),
            ]
        )
    for col in "ABCDEFGH":
        payroll.column_dimensions[col].width = 22

    summary = wb.create_sheet("Resumen")
    rate = preference_rate(preference_results(problem, proposal))
    rows = [
        ("Clínica", clinic.raw["tenant"]["name"]),
        ("Periodo", clinic.raw["period"]["label"]),
        ("Versión", proposal.strategy.label if proposal.strategy else ""),
        ("Costo total estimado", round(cost.total)),
        ("Recargos nocturnos", round(cost.night_surcharge)),
        ("Recargos dominicales y festivos", round(cost.holiday_surcharge)),
        ("Preferencias cumplidas", f"{rate:.0%}"),
        ("Nota", "Valores de reglas laborales por verificar. Datos ficticios."),
    ]
    for row in rows:
        summary.append(row)
        summary.cell(row=summary.max_row, column=1).font = BOLD
    summary.column_dimensions["A"].width = 34
    summary.column_dimensions["B"].width = 50

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
