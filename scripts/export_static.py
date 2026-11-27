"""Exporta la demo a HTML estático navegable (para abrir desde el teléfono).

Uso: python -m scripts.export_static <carpeta_salida>
"""

import base64
import json
import re
import sys
from datetime import date
from pathlib import Path

from app import create_app
from app.config import Config
from app.demo.state import get_state, reset_state
from app.demo.whatsapp import reply
from app.routes.demo import WEEKDAY_NAMES, WHATSAPP_SUGGESTIONS
from engine.explain import explain

MEETING_DAY = date(2026, 12, 3)
ABSENCE_EXAMPLE = {"employee_id": "EMP-002", "kind": "Incapacidad"}


class ExportConfig(Config):
    STATIC_EXPORT = True


def page_name(path: str) -> str:
    path = path.split("#")[0]
    if path in ("", "/"):
        return "inicio.html"
    match = re.fullmatch(r"/\?v=(\d+)", path)
    if match:
        return "inicio.html" if match.group(1) == "0" else f"inicio-{match.group(1)}.html"
    match = re.fullmatch(r"/cuadro/(\d+)(?:\?servicio=(\w+))?", path)
    if match:
        index, service = match.groups()
        return f"cuadro-{index}.html" if service in (None, "todos") else f"cuadro-{index}-{service}.html"
    match = re.fullmatch(r"/exportar/(\d+)", path)
    if match:
        return f"cuadro-{match.group(1)}.xlsx"
    if path.startswith("/static/"):
        return path[1:]
    return path.split("?")[0].strip("/").replace("/", "-") + ".html"


def rewrite(html: str, roster_index: int | None = None) -> str:
    def fix(m: re.Match) -> str:
        target = m.group(2)
        if target.startswith("?servicio=") and roster_index is not None:
            target = f"/cuadro/{roster_index}{target}"
        if target.startswith(("/", "?")):
            return f'{m.group(1)}="{page_name(target)}"'
        return m.group(0)

    return re.sub(r'(href|action)="([^"]*)"', fix, html)


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    app = create_app(ExportConfig)
    client = app.test_client()
    reset_state()
    state = get_state()
    state.today_override = MEETING_DAY

    client.post("/generar")
    problem = state.problem

    pages = ["/", "/clinica", "/equipo", "/generar", "/comparar"]
    pages += [f"/?v={i}" for i in range(1, len(state.proposals))]

    def save(path: str) -> None:
        html = client.get(path).get_data(as_text=True)
        index = int(path.split("/")[2].split("?")[0]) if path.startswith("/cuadro/") else None
        (out / page_name(path)).write_text(rewrite(html, index), encoding="utf-8")

    for path in pages:
        save(path)
    client.post("/publicar/0")
    save("/publicado")

    for i, proposal in enumerate(state.proposals):
        data = {
            f"{e.id}/{d}": {
                **explain(problem, proposal, e.id, d),
                "date": f"{WEEKDAY_NAMES[problem.weekday_of(d)]} {d + 1}",
            }
            for e in problem.employees
            for d in range(problem.days)
        }
        (out / f"explicaciones-{i}.json").write_text(json.dumps(data, ensure_ascii=False))

    (out / "whatsapp.html").write_text(
        rewrite(client.get("/whatsapp").get_data(as_text=True)), encoding="utf-8"
    )
    replies = {e.id: {} for e in problem.employees}
    for e in problem.employees:
        for text in WHATSAPP_SUGGESTIONS:
            replies[e.id][text] = reply(state, e.id, text)
    (out / "whatsapp.json").write_text(json.dumps(replies, ensure_ascii=False))

    day = MEETING_DAY.day
    html = client.post("/novedades", data={**ABSENCE_EXAMPLE, "day": day}).get_data(as_text=True)
    (out / "novedades.html").write_text(rewrite(html), encoding="utf-8")

    static = Path(app.static_folder)
    css = (static / "luna.css").read_text(encoding="utf-8")
    logo = base64.b64encode((static / "img" / "logo_joint_blanco.png").read_bytes()).decode()
    link = '<link rel="stylesheet" href="static/luna.css">'
    for page in out.glob("*.html"):
        html = page.read_text(encoding="utf-8").replace(link, f"<style>{css}</style>")
        html = html.replace("/static/img/logo_joint_blanco.png", f"data:image/png;base64,{logo}")
        page.write_text(html, encoding="utf-8")

    # Página de entrada sin esqueleto propio (el visor agrega doctype, head y body).
    home = (out / "inicio.html").read_text(encoding="utf-8")
    title = re.search(r"<title>.*?</title>", home, re.S).group(0)
    body = re.search(r"<body>(.*)</body>", home, re.S).group(1)
    head = re.search(r"<head>(.*)</head>", home, re.S).group(1)
    fonts = "\n".join(re.findall(r'<link rel="(?:preconnect|stylesheet)" href="https://fonts[^>]*>', head))
    entry = f"{title}\n{fonts}\n<style>{css}</style>\n{body}"
    (out / "index.html").write_text(entry, encoding="utf-8")
    print(f"Exportado en {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "build/demo"))
