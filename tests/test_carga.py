import hashlib
import statistics

import pandas as pd
import pytest

from app import create_app
from app.models import Inconsistencia, Muestra, Sondaje
from app.services.carga import (
    MAESTRO,
    RESULTADOS,
    aplicar_reglas,
    leer_maestro,
    leer_resultados,
)
from tests.conftest import INSUMOS


def _hash(ruta):
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


# ---------- cifras de control sobre la BD ----------
def test_conteos_bd(app):
    with app.app_context():
        assert Sondaje.query.count() == 12
        assert Muestra.query.count() == 174
        assert Inconsistencia.query.count() == 3


def test_filas_excel_laboratorio():
    assert len(leer_resultados(INSUMOS / RESULTADOS)) == 176
    assert len(leer_maestro(INSUMOS / MAESTRO)) == 12


def test_inconsistencias_exactas(app):
    with app.app_context():
        obtenidas = {
            (i.tipo, i.muestra_id, i.sondaje_id) for i in Inconsistencia.query.all()
        }
    assert obtenidas == {
        ("R1", "M-4175", "DDH-099"),
        ("R1", "M-4176", "DDH-099"),
        ("R2", None, "DDH-012"),
    }


def test_excluidas_y_sondaje_sin_muestras(app):
    with app.app_context():
        assert Muestra.query.filter(Muestra.muestra_id.in_(["M-4175", "M-4176"])).count() == 0
        assert db_get(Sondaje, "DDH-012") is not None
        assert Muestra.query.filter_by(sondaje_id="DDH-012").count() == 0


def db_get(modelo, sondaje_id):
    return modelo.query.filter_by(sondaje_id=sondaje_id).first()


# ---------- R3 ----------
def test_r3_en_bd(app):
    with app.app_context():
        for m in Muestra.query.all():
            if m.au_original == -99:
                assert m.au_gpt == 0.01
            else:
                assert m.au_original == m.au_gpt
            assert m.au_gpt >= 0


def test_r3_ids_excel_coinciden_con_bd(app):
    df = leer_resultados(INSUMOS / RESULTADOS)
    ids_excel = set(df.loc[df["Au_gpt"] == -99, "Muestra_ID"])
    assert ids_excel == {"M-4102", "M-4128"}
    with app.app_context():
        ids_bd = {m.muestra_id for m in Muestra.query.filter(Muestra.au_original == -99)}
    assert ids_bd == ids_excel


# ---------- estadísticos ----------
def test_estadisticos_control(app):
    with app.app_context():
        leyes = [m.au_gpt for m in Muestra.query.all()]
        maxima = Muestra.query.order_by(Muestra.au_gpt.desc()).first()
        max_id, max_sond, max_val = maxima.muestra_id, maxima.sondaje_id, maxima.au_gpt
    assert sum(leyes) / len(leyes) == pytest.approx(3.55, abs=0.01)
    assert statistics.median(leyes) == pytest.approx(1.355, abs=0.01)
    assert max_val == pytest.approx(95.40, abs=0.01)
    assert (max_id, max_sond) == ("M-4026", "DDH-002")


# ---------- unitarias de aplicar_reglas (sin BD) ----------
def _maestro(ids):
    return pd.DataFrame(
        [
            {
                "Sondaje_ID": i, "Zona": "Veta Norte", "Este_m": 1.0, "Norte_m": 2.0,
                "Elevacion_m": 3.0, "Azimut_grados": 4.0, "Buzamiento_grados": -60.0,
                "Profundidad_m": 100.0,
            }
            for i in ids
        ]
    )


def _resultados(filas):
    return pd.DataFrame(
        [
            {
                "Muestra_ID": m, "Sondaje_ID": s, "Desde_m": 0.0, "Hasta_m": 1.0,
                "Au_gpt": au, "Lote_Laboratorio": "L1",
            }
            for m, s, au in filas
        ]
    )


def test_reglas_todo_consistente():
    r = aplicar_reglas(_maestro(["A", "B"]), _resultados([("M1", "A", 1.0), ("M2", "B", 2.0)]))
    assert r["inconsistencias"] == []
    assert len(r["muestras"]) == 2 and len(r["sondajes"]) == 2


def test_reglas_r1_sondaje_inexistente():
    r = aplicar_reglas(_maestro(["A"]), _resultados([("M1", "A", 1.0), ("M2", "X", 5.0)]))
    assert [m["muestra_id"] for m in r["muestras"]] == ["M1"]
    assert [(i["tipo"], i["muestra_id"], i["sondaje_id"]) for i in r["inconsistencias"]] == [
        ("R1", "M2", "X")
    ]


def test_reglas_r2_sondaje_sin_muestras():
    r = aplicar_reglas(_maestro(["A", "B"]), _resultados([("M1", "A", 1.0)]))
    assert [(i["tipo"], i["muestra_id"], i["sondaje_id"]) for i in r["inconsistencias"]] == [
        ("R2", None, "B")
    ]


def test_reglas_r3_menos_99():
    r = aplicar_reglas(_maestro(["A"]), _resultados([("M1", "A", -99)]))
    m = r["muestras"][0]
    assert m["au_original"] == -99 and m["au_gpt"] == 0.01


@pytest.mark.parametrize("valor", [-98, 0, 0.01, -99.5])
def test_reglas_r3_otros_valores_no_se_convierten(valor):
    r = aplicar_reglas(_maestro(["A"]), _resultados([("M1", "A", valor)]))
    m = r["muestras"][0]
    assert m["au_gpt"] == valor and m["au_original"] == valor


# ---------- insumos intactos e idempotencia ----------
def test_insumos_no_se_modifican(db_uri):
    archivos = [INSUMOS / MAESTRO, INSUMOS / RESULTADOS]
    antes = [_hash(a) for a in archivos]
    create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": db_uri, "INSUMOS_DIR": str(INSUMOS)})
    assert [_hash(a) for a in archivos] == antes


def test_recarga_idempotente(db_uri):
    cfg = {"TESTING": True, "SQLALCHEMY_DATABASE_URI": db_uri, "INSUMOS_DIR": str(INSUMOS)}
    create_app(cfg)
    app = create_app(cfg)
    with app.app_context():
        assert (Sondaje.query.count(), Muestra.query.count(), Inconsistencia.query.count()) == (12, 174, 3)
