"""Aplicación web de LUNA (Flask)."""

from flask import Flask

from app.config import Config


def create_app(config: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config)

    from app.routes.demo import bp as demo_bp
    from app.routes.health import bp as health_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(demo_bp)
    return app
