"""Tests de capping: cifras de control (CLAUDE.md), reglas R4-R7 y filtros HTTP."""
import re
import statistics

import pytest

from app.models import Muestra
from app.services import capping, consultas

P95 = (capping.METODO_PERCENTIL, 95)
K2 = (capping.METODO_MEDIA_K_SIGMA, 2)


def resumen_zona(app, zona, metodo, parametro):
    with app.app_context():
        muestras = consultas.muestras_por_zona(zona)
        leyes = [m["au_gpt"] for m in muestras]
        ids = [(m["muestra_id"], m["sondaje_id"]) for m in muestras]
        return capping.resumen(leyes, metodo, parametro, ids)


# ------------------------------------------------------------ A) cifras de control (servicio)
def test_todas_estadisticos_basicos(app):
    r = resumen_zona(app, "Todas", *P95)
    assert r["n"] == 174
    assert r["media"] == pytest.approx(3.55, abs=0.01)
    assert r["mediana"] == pytest.approx(1.355, abs=0.01)
    assert r["maximo"] == pytest.approx(95.40, abs=0.01)
    assert r["maximo_muestra_id"] == "M-4026"
    assert r["maximo_sondaje_id"] == "DDH-002"


def test_todas_percentil_95(app):
    r = resumen_zona(app, "Todas", *P95)
    assert r["umbral"] == pytest.approx(8.36, abs=0.01)
    assert r["outliers"] == 9
    assert r["media_capeada"] == pytest.approx(2.23, abs=0.01)
    assert r["variacion_pct"] == pytest.approx(-37.3, abs=0.1)


def test_todas_media_mas_2_sigma(app):
    r = resumen_zona(app, "Todas", *K2)
    assert r["umbral"] == pytest.approx(22.09, abs=0.01)
    assert r["outliers"] == 6
    assert r["media_capeada"] == pytest.approx(2.76, abs=0.01)


def test_veta_norte_percentil_95(app):
    r = resumen_zona(app, "Veta Norte", *P95)
    assert r["n"] == 122
    assert r["umbral"] == pytest.approx(8.83, abs=0.01)
    assert r["outliers"] == 7
    assert r["media_capeada"] == pytest.approx(2.52, abs=0.01)


def test_veta_sur_percentil_95(app):
    r = resumen_zona(app, "Veta Sur", *P95)
    assert r["n"] == 52
    assert r["umbral"] == pytest.approx(6.02, abs=0.01)
    assert r["outliers"] == 3
    assert r["media_capeada"] == pytest.approx(1.47, abs=0.01)


# ------------------------------------------------------------ A) cifras de control (página)
def tarjetas(html):
    """Devuelve {etiqueta: valor} de las tarjetas (valor junto a su etiqueta)."""
    pares = re.findall(
        r'<div class="valor">\s*(.*?)\s*</div>\s*<div class="etiqueta">\s*(.*?)\s*</div>', html, re.S
    )
    return {re.sub(r"\s+", " ", e): v for v, e in pares}


def tarjeta(html, prefijo):
    for etiqueta, valor in tarjetas(html).items():
        if etiqueta.startswith(prefijo):
            return valor
    raise AssertionError(f"No hay tarjeta con etiqueta {prefijo!r}")


def filas_tabla_outliers(html):
    seccion = html.split("<h2>Outliers</h2>")[1].split("<h2")[0]
    cuerpo = re.search(r"<tbody>(.*?)</tbody>", seccion, re.S).group(1)
    filas = []
    for tr in re.findall(r"<tr>(.*?)</tr>", cuerpo, re.S):
        filas.append([re.sub(r"<.*?>", "", td).strip() for td in re.findall(r"<td.*?</td>", tr, re.S)])
    return filas


def get_html(client, url):
    r = client.get(url)
    assert r.status_code == 200
    return r.get_data(as_text=True)


def test_pagina_todas_p95(client):
    html = get_html(client, "/")
    assert tarjeta(html, "Umbral") == "8.36"
    assert tarjeta(html, "Outliers") == "9"
    assert tarjeta(html, "Muestras en el análisis") == "174"
    assert tarjeta(html, "Media (g/t") == "3.55"
    assert tarjeta(html, "Media capeada") == "2.23"
    assert tarjeta(html, "Variación") == "-37.3 %"
    assert tarjeta(html, "Máximo") == "95.40"
    filas = filas_tabla_outliers(html)
    assert len(filas) == 9
    assert filas[0][0] == "M-4026" and filas[0][1] == "DDH-002"
    assert filas[0][5] == "95.40" and filas[0][6] == "8.36"
    leyes = [float(f[5]) for f in filas]
    assert leyes == sorted(leyes, reverse=True)


def test_pagina_veta_norte(client):
    html = get_html(client, "/?zona=Veta Norte")
    assert tarjeta(html, "Umbral") == "8.83"
    assert tarjeta(html, "Outliers") == "7"
    filas = filas_tabla_outliers(html)
    assert len(filas) == 7
    assert {f[2] for f in filas} == {"Veta Norte"}


def test_pagina_veta_sur(client):
    html = get_html(client, "/?zona=Veta Sur")
    assert tarjeta(html, "Umbral") == "6.02"
    assert tarjeta(html, "Outliers") == "3"
    filas = filas_tabla_outliers(html)
    assert len(filas) == 3
    assert {f[2] for f in filas} == {"Veta Sur"}


def test_pagina_media_k_sigma_2(client):
    html = get_html(client, "/?metodo=media_k_sigma&parametro=2")
    assert tarjeta(html, "Umbral") == "22.09"
    assert tarjeta(html, "Outliers") == "6"
    assert tarjeta(html, "Media capeada") == "2.76"
    assert len(filas_tabla_outliers(html)) == 6


# ------------------------------------------------------------ B) reglas puras
def test_ley_igual_al_umbral_no_es_outlier():
    r = capping.aplicar([1.0, 5.0, 5.0001], 5.0)
    assert r[1]["es_outlier"] is False
    assert r[1]["au_capped"] == 5.0
    assert r[0]["es_outlier"] is False and r[0]["au_capped"] == 1.0


def test_ley_mayor_al_umbral_es_outlier_y_se_capea():
    r = capping.aplicar([5.0, 7.5], 5.0)
    assert r[1]["es_outlier"] is True
    assert r[1]["au_capped"] == 5.0
    assert r[1]["au_gpt"] == 7.5


def test_aplicar_no_muta_entrada_y_conserva_au_gpt():
    leyes = [0.5, 3.0, 10.0, 99.0]
    copia = list(leyes)
    r = capping.aplicar(leyes, 3.0)
    assert leyes == copia
    assert [f["au_gpt"] for f in r] == copia
    assert all(f["au_capped"] <= 3.0 for f in r)
    assert [f["es_outlier"] for f in r] == [False, False, True, True]


def test_percentile_inc_cuatro_valores():
    assert capping.umbral([1, 2, 3, 4], capping.METODO_PERCENTIL, 95) == pytest.approx(3.85)


def test_percentile_inc_no_depende_del_orden():
    assert capping.umbral([4, 1, 3, 2], capping.METODO_PERCENTIL, 95) == pytest.approx(3.85)


def test_percentile_un_solo_valor():
    for p in capping.PARAMETROS[capping.METODO_PERCENTIL]:
        assert capping.umbral([2.5], capping.METODO_PERCENTIL, p) == 2.5


def test_media_k_sigma_desviacion_muestral():
    leyes = [2, 4, 4, 4, 5, 5, 7, 9]  # media 5; suma de cuadrados 32 -> s = sqrt(32/7)
    s = (32 / 7) ** 0.5
    assert capping.umbral(leyes, capping.METODO_MEDIA_K_SIGMA, 2) == pytest.approx(5 + 2 * s)
    # la desviación poblacional (2.0) daría 9.0: no debe usarse
    assert capping.umbral(leyes, capping.METODO_MEDIA_K_SIGMA, 2) != pytest.approx(9.0)


def test_umbral_metodo_invalido():
    with pytest.raises(ValueError):
        capping.umbral([1, 2, 3], "x", 95)


@pytest.mark.parametrize(
    "metodo,parametro",
    [
        (capping.METODO_PERCENTIL, 50),
        (capping.METODO_PERCENTIL, 100),
        (capping.METODO_MEDIA_K_SIGMA, 95),
        (capping.METODO_MEDIA_K_SIGMA, 1),
        (capping.METODO_PERCENTIL, "abc"),
    ],
)
def test_umbral_parametro_no_permitido(metodo, parametro):
    with pytest.raises(ValueError):
        capping.umbral([1, 2, 3, 4], metodo, parametro)


@pytest.mark.parametrize("metodo", [capping.METODO_PERCENTIL, capping.METODO_MEDIA_K_SIGMA])
def test_umbral_lista_vacia(metodo):
    with pytest.raises(ValueError):
        capping.umbral([], metodo, capping.PARAMETRO_DEFECTO[metodo])


@pytest.mark.parametrize("p", [90, 95, 97.5, 99])
def test_percentiles_permitidos(p):
    assert capping.umbral([1, 2, 3, 4, 5], capping.METODO_PERCENTIL, p) <= 5


@pytest.mark.parametrize("k", [2, 2.5, 3])
def test_k_permitidos(k):
    leyes = [1, 2, 3, 4, 5]
    esperado = 3 + k * statistics.stdev(leyes)
    assert capping.umbral(leyes, capping.METODO_MEDIA_K_SIGMA, k) == pytest.approx(esperado)


def test_defectos():
    assert capping.PARAMETRO_DEFECTO == {capping.METODO_PERCENTIL: 95, capping.METODO_MEDIA_K_SIGMA: 2}


def test_capear_todas_p95_no_supera_umbral_y_no_toca_la_bd(app):
    with app.app_context():
        antes = sorted((m.muestra_id, m.au_original, m.au_gpt) for m in Muestra.query.all())
        muestras = consultas.muestras_por_zona("Todas")
        leyes = [m["au_gpt"] for m in muestras]
        u = capping.umbral(leyes, *P95)
        aplicado = capping.aplicar(leyes, u)
        assert max(f["au_capped"] for f in aplicado) <= u
        assert sum(f["es_outlier"] for f in aplicado) == 9
        consultas.analisis("Todas", *P95)  # consultar tampoco modifica nada
        despues = sorted((m.muestra_id, m.au_original, m.au_gpt) for m in Muestra.query.all())
        assert antes == despues
        assert len(antes) == 174
        assert max(a[2] for a in antes) == pytest.approx(95.40, abs=0.01)


# ------------------------------------------------------------ C) HTTP
def test_get_sin_parametros_usa_defectos(client):
    html = get_html(client, "/")
    assert re.search(r'<option value="Todas"\s+selected', html)
    assert re.search(r'<option value="percentil"\s+selected', html)
    assert "Percentil, P = 95" in re.sub(r"\s+", " ", html)


@pytest.mark.parametrize(
    "query",
    [
        "parametro=50",
        "parametro=abc",
        "metodo=x",
        "zona=Centro",
        "metodo=media_k_sigma&parametro=95",
    ],
)
def test_parametros_invalidos_400(client, query):
    assert client.get(f"/?{query}").status_code == 400


def test_tabla_inconsistencias_visible_en_veta_sur(client):
    html = get_html(client, "/?zona=Veta Sur")
    seccion = html.split("Inconsistencias detectadas")[1]
    for texto in ("M-4175", "M-4176", "DDH-012", "DDH-099"):
        assert texto in seccion
