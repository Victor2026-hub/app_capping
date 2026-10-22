from pathlib import Path

import pytest

from app import create_app

INSUMOS = Path(__file__).resolve().parent.parent / "Insumos"


@pytest.fixture
def db_uri(tmp_path):
    return f"sqlite:///{tmp_path / 'test.db'}"


@pytest.fixture
def app(db_uri):
    return create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": db_uri,
            "INSUMOS_DIR": str(INSUMOS),
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()
