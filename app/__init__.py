"""Fábrica de la aplicación capping_web."""
from pathlib import Path

from flask import Flask

from app.extensions import db

PROYECTO = Path(__file__).resolve().parent.parent


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    app.config.from_mapping(
        SECRET_KEY="dev",
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{Path(app.instance_path) / 'capping.db'}",
        INSUMOS_DIR=str(PROYECTO / "Insumos"),
    )
    if test_config:
        app.config.from_mapping(test_config)

    db.init_app(app)

    with app.app_context():
        from app.services.carga import cargar_datos

        cargar_datos(app.config["INSUMOS_DIR"])

    from app.controllers.main_controller import main_bp

    app.register_blueprint(main_bp)

    return app
