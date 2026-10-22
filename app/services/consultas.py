"""Consultas de lectura para los controllers."""
from sqlalchemy import func, select

from app.extensions import db
from app.models import Inconsistencia, Muestra, Sondaje
from app.services import capping


def contadores() -> dict:
    def contar(modelo):
        return db.session.scalar(select(func.count()).select_from(modelo))

    return {
        "sondajes": contar(Sondaje),
        "muestras": contar(Muestra),
        "inconsistencias": contar(Inconsistencia),
    }


def listar_inconsistencias() -> list[Inconsistencia]:
    return list(db.session.scalars(
        select(Inconsistencia).order_by(Inconsistencia.tipo, Inconsistencia.id)
    ))


ZONAS = ("Todas", "Veta Norte", "Veta Sur")
ETIQUETAS_METODO = {
    capping.METODO_PERCENTIL: "Percentil",
    capping.METODO_MEDIA_K_SIGMA: "Media + k·σ",
}


def leer_filtros(zona, metodo, parametro) -> tuple[str, str, float]:
    """Valida los filtros de la página de inicio y aplica los valores por defecto.
    Lanza ValueError (mensaje en español) si alguno no es válido."""
    zona = zona or "Todas"
    if zona not in ZONAS:
        raise ValueError(f"Zona no válida: {zona!r}. Use una de: {', '.join(ZONAS)}.")
    metodo = metodo or capping.METODO_PERCENTIL
    if metodo not in capping.METODOS:
        raise ValueError(f"Método no válido: {metodo!r}. Use uno de: {', '.join(capping.METODOS)}.")
    permitidos = capping.PARAMETROS[metodo]
    if parametro in (None, ""):
        return zona, metodo, capping.PARAMETRO_DEFECTO[metodo]
    try:
        valor = float(parametro)
    except ValueError:
        raise ValueError(f"Parámetro no numérico: {parametro!r}.") from None
    for p in permitidos:
        if valor == float(p):
            return zona, metodo, p
    raise ValueError(
        f"Parámetro {parametro!r} no válido para el método {metodo}. "
        f"Valores permitidos: {', '.join(str(p) for p in permitidos)}."
    )


def muestras_por_zona(zona: str) -> list[dict]:
    """Muestras válidas (con datos del sondaje) de la zona, ordenadas por Muestra_ID."""
    consulta = select(Muestra, Sondaje.zona).join(Sondaje, Muestra.sondaje_id == Sondaje.sondaje_id)
    if zona != "Todas":
        consulta = consulta.where(Sondaje.zona == zona)
    consulta = consulta.order_by(Muestra.muestra_id)
    return [
        {
            "muestra_id": m.muestra_id,
            "sondaje_id": m.sondaje_id,
            "zona": z,
            "desde_m": m.desde_m,
            "hasta_m": m.hasta_m,
            "au_gpt": m.au_gpt,
            "au_original": m.au_original,
            "lote": m.lote,
        }
        for m, z in db.session.execute(consulta)
    ]


def filas_outliers(muestras: list[dict], aplicado: list[dict]) -> list[dict]:
    """Une muestras con el resultado de capping.aplicar, deja los outliers y los ordena
    por ley original descendente."""
    filas = [
        {**m, "au_capped": r["au_capped"]}
        for m, r in zip(muestras, aplicado)
        if r["es_outlier"]
    ]
    return sorted(filas, key=lambda f: f["au_gpt"], reverse=True)


def analisis(zona: str, metodo: str, parametro) -> dict:
    """Resumen de capping y tabla de outliers para los filtros dados."""
    muestras = muestras_por_zona(zona)
    leyes = [m["au_gpt"] for m in muestras]
    ids = [(m["muestra_id"], m["sondaje_id"]) for m in muestras]
    resumen = capping.resumen(leyes, metodo, parametro, ids)
    aplicado = capping.aplicar(leyes, resumen["umbral"])
    return {
        "resumen": resumen,
        "outliers": filas_outliers(muestras, aplicado),
        "originales": leyes,
        "capeadas": [r["au_capped"] for r in aplicado],
    }


def etiqueta_parametro(metodo: str, parametro) -> str:
    return ("P = " if metodo == capping.METODO_PERCENTIL else "k = ") + str(parametro)


def recargar_datos(insumos_dir) -> str:
    """Relee Insumos/, reconstruye la BD y devuelve el mensaje de resultado.
    Lanza la excepción original si la carga falla (el controller la convierte en flash)."""
    from app.services.carga import cargar_datos

    try:
        cargar_datos(insumos_dir)
    except Exception:
        db.session.rollback()
        raise
    c = contadores()
    return (f"Datos recargados: {c['sondajes']} sondajes, {c['muestras']} muestras válidas, "
            f"{c['inconsistencias']} inconsistencias.")
