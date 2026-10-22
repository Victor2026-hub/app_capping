"""Capping de leyes de oro: reglas R4 a R7 como funciones puras (sin Flask ni BD)."""
import math
import statistics

METODO_PERCENTIL = "percentil"
METODO_MEDIA_K_SIGMA = "media_k_sigma"
METODOS = (METODO_PERCENTIL, METODO_MEDIA_K_SIGMA)
PARAMETROS = {METODO_PERCENTIL: (90, 95, 97.5, 99), METODO_MEDIA_K_SIGMA: (2, 2.5, 3)}
PARAMETRO_DEFECTO = {METODO_PERCENTIL: 95, METODO_MEDIA_K_SIGMA: 2}


def _parametro_valido(metodo, parametro) -> float:
    """Valida método y parámetro (comparación numérica) y devuelve el parámetro como float."""
    if metodo not in METODOS:
        raise ValueError(f"Método no válido: {metodo!r}. Use uno de: {', '.join(METODOS)}.")
    try:
        valor = float(parametro)
    except (TypeError, ValueError):
        raise ValueError(f"Parámetro no numérico: {parametro!r}.") from None
    if isinstance(parametro, bool) or valor not in {float(p) for p in PARAMETROS[metodo]}:
        permitidos = ", ".join(str(p) for p in PARAMETROS[metodo])
        raise ValueError(
            f"Parámetro {parametro!r} no válido para el método {metodo}. Valores permitidos: {permitidos}."
        )
    return valor


def umbral(leyes, metodo, parametro) -> float:
    """Umbral de capping. R4: percentil P (igual a PERCENTILE.INC, interpolación lineal
    sobre n-1). R5: media + k·σ con σ muestral (igual a STDEV.S, ddof=1)."""
    valor = _parametro_valido(metodo, parametro)
    datos = [float(x) for x in leyes]
    if not datos:
        raise ValueError("No hay leyes para calcular el umbral.")
    if metodo == METODO_PERCENTIL:
        datos.sort()
        pos = (len(datos) - 1) * valor / 100.0
        i = int(math.floor(pos))
        if i >= len(datos) - 1:
            return datos[-1]
        return datos[i] + (pos - i) * (datos[i + 1] - datos[i])
    if len(datos) < 2:
        raise ValueError("El método media + k·σ requiere al menos 2 leyes.")
    return statistics.fmean(datos) + valor * statistics.stdev(datos)


def aplicar(leyes, umbral) -> list[dict]:
    """R6 y R7: outlier si ley > umbral (estricto); au_capped = min(ley, umbral).
    No modifica la entrada ni la ley original (au_gpt)."""
    return [
        {"au_gpt": ley, "es_outlier": ley > umbral, "au_capped": min(ley, umbral)}
        for ley in leyes
    ]


def resumen(leyes, metodo, parametro, ids=None) -> dict:
    """Estadísticos, umbral (R4/R5), outliers (R6) y media capeada. Sin redondeo.
    ids[i] = (muestra_id, sondaje_id) alineado con leyes."""
    leyes = list(leyes)
    u = umbral(leyes, metodo, parametro)
    filas = aplicar(leyes, u)
    media = statistics.fmean(leyes)
    media_cap = statistics.fmean(f["au_capped"] for f in filas)
    i_max = max(range(len(leyes)), key=leyes.__getitem__)
    return {
        "n": len(leyes),
        "media": media,
        "mediana": statistics.median(leyes),
        "maximo": leyes[i_max],
        "maximo_muestra_id": ids[i_max][0] if ids is not None else None,
        "maximo_sondaje_id": ids[i_max][1] if ids is not None else None,
        "metodo": metodo,
        "parametro": parametro,
        "umbral": u,
        "outliers": sum(f["es_outlier"] for f in filas),
        "media_capeada": media_cap,
        "variacion_pct": (media_cap - media) / media * 100 if media else 0.0,
    }
