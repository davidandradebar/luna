# LUNA

Cuadro de turnos inteligente para el personal asistencial de clínicas e IPS en Colombia.

> El cuadro del mes listo en minutos, legal, justo, con las preferencias del equipo y con su costo calculado antes de publicarlo.

## Estructura

| Carpeta | Contenido |
|---|---|
| `app/` | Aplicación web (Flask 3), demo guiada, modelos, reglas laborales y trabajos RQ |
| `engine/` | Motor de asignación con OR-Tools CP-SAT, costos, indicadores y explicaciones; independiente de Flask |
| `bot/` | Intérprete de mensajes de WhatsApp (simulado en la demo) |
| `docs/` | Modelo de dominio y reglas de negocio |
| `fixtures/` | Datos ficticios para desarrollo y pruebas |
| `tests/` | Pruebas con pytest |

## Demo guiada

Recorrido en 5 pasos con una clínica ficticia: configurar la clínica, ver el equipo y sus preferencias, generar 3 cuadros con el motor, comparar costo y equidad, y publicar. Incluye explicación por turno, novedades con reemplazos, WhatsApp simulado y exportación a Excel.

```bash
pip install -r requirements.txt
flask --app wsgi run    # http://localhost:5000
```

Guion de presentación en [docs/guion_demo.md](docs/guion_demo.md).

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
