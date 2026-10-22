"""Carga de los Excel de Insumos/ y aplicación de las reglas R1 a R3.

La lectura y las reglas son funciones sin BD; solo `cargar_datos` escribe.
"""
from pathlib import Path

import pandas as pd

from app.extensions import db
from app.models import Inconsistencia, Muestra, Sondaje

MAESTRO = "Maestro_Sondajes.xlsx"
RESULTADOS = "Resultados_Laboratorio.xlsx"
VALOR_BAJO_LIMITE = -99
AU_BAJO_LIMITE = 0.01


def leer_maestro(ruta) -> pd.DataFrame:
    return pd.read_excel(ruta, sheet_name=0)


def leer_resultados(ruta) -> pd.DataFrame:
    return pd.read_excel(ruta, sheet_name=0)


def aplicar_reglas(maestro: pd.DataFrame, resultados: pd.DataFrame) -> dict:
    """Aplica R1, R2 y R3. Devuelve dict con listas de dicts:
    {"sondajes": [...], "muestras": [...], "inconsistencias": [...]}.
    """
    sondajes = [
        {
            "sondaje_id": str(f.Sondaje_ID),
            "zona": str(f.Zona),
            "este_m": float(f.Este_m),
            "norte_m": float(f.Norte_m),
            "elevacion_m": float(f.Elevacion_m),
            "azimut": float(f.Azimut_grados),
            "buzamiento": float(f.Buzamiento_grados),
            "profundidad_m": float(f.Profundidad_m),
        }
        for f in maestro.itertuples(index=False)
    ]
    ids_maestro = {s["sondaje_id"] for s in sondajes}

    muestras, inconsistencias = [], []
    for f in resultados.itertuples(index=False):
        muestra_id, sondaje_id = str(f.Muestra_ID), str(f.Sondaje_ID)
        if sondaje_id not in ids_maestro:  # R1
            inconsistencias.append({
                "tipo": "R1",
                "muestra_id": muestra_id,
                "sondaje_id": sondaje_id,
                "descripcion": (
                    f"La muestra {muestra_id} referencia al sondaje {sondaje_id}, "
                    "que no existe en el maestro de sondajes; se excluye del análisis."
                ),
            })
            continue
        original = float(f.Au_gpt)
        au = AU_BAJO_LIMITE if original == VALOR_BAJO_LIMITE else original  # R3
        muestras.append({
            "muestra_id": muestra_id,
            "sondaje_id": sondaje_id,
            "desde_m": float(f.Desde_m),
            "hasta_m": float(f.Hasta_m),
            "au_original": original,
            "au_gpt": au,
            "lote": str(f.Lote_Laboratorio),
        })

    con_muestras = {m["sondaje_id"] for m in muestras}
    for s in sondajes:  # R2
        if s["sondaje_id"] not in con_muestras:
            inconsistencias.append({
                "tipo": "R2",
                "muestra_id": None,
                "sondaje_id": s["sondaje_id"],
                "descripcion": (
                    f"El sondaje {s['sondaje_id']} está en el maestro pero no tiene "
                    "muestras en los resultados de laboratorio."
                ),
            })
    return {"sondajes": sondajes, "muestras": muestras, "inconsistencias": inconsistencias}


def cargar_datos(insumos_dir) -> dict:
    """Reconstruye la BD (drop_all + create_all) desde los Excel y la llena.
    Requiere contexto de aplicación. Devuelve el dict de aplicar_reglas.
    """
    insumos = Path(insumos_dir)
    datos = aplicar_reglas(
        leer_maestro(insumos / MAESTRO), leer_resultados(insumos / RESULTADOS)
    )
    db.drop_all()
    db.create_all()
    db.session.add_all(Sondaje(**s) for s in datos["sondajes"])
    db.session.add_all(Muestra(**m) for m in datos["muestras"])
    db.session.add_all(Inconsistencia(**i) for i in datos["inconsistencias"])
    db.session.commit()
    return datos
