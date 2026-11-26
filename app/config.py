import os


class Config:
    """Configuración leída del entorno. Ver .env.example."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "")
    DATABASE_URL = os.environ.get("DATABASE_URL", "")
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    RQ_QUEUE = os.environ.get("RQ_QUEUE", "rosters")


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test"  # noqa: S105 - valor fijo solo para pruebas
