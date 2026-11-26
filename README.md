# LUNA

Cuadro de turnos inteligente para el personal asistencial de clínicas e IPS en Colombia.

> El cuadro del mes listo en minutos, legal, justo, con las preferencias del equipo y con su costo calculado antes de publicarlo.

## Estructura

| Carpeta | Contenido |
|---|---|
| `app/` | Aplicación web (Flask 3), modelos, reglas laborales y trabajos RQ |
| `engine/` | Motor de asignación con OR-Tools CP-SAT, independiente de Flask |
| `bot/` | Integración de WhatsApp vía la plataforma de AURA (pendiente) |
| `docs/` | Modelo de dominio y reglas de negocio |
| `fixtures/` | Datos ficticios para desarrollo y pruebas |
| `tests/` | Pruebas con pytest |

## Requisitos

- Python 3.12
- Docker y Docker Compose (PostgreSQL 16, Redis 7)

## Desarrollo local

```bash
cp .env.example .env          # completar valores locales
docker compose up --build     # web en http://localhost:8000/health
```

Sin Docker:

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
ruff check . && ruff format --check .
pytest
```

## Reglas del repositorio

- Commits, PRs, comentarios y documentación en español; identificadores de código en inglés.
- Nunca subir datos reales de personas (nombres, cédulas, teléfonos, correos) ni secretos. Usar solo datos ficticios.
- Las reglas laborales son parametrizables por tenant y régimen, con vigencia por fecha. Nunca se escriben en el código.
- La CI ejecuta lint (ruff), pruebas (pytest) y escaneo de secretos (gitleaks) en cada PR.
