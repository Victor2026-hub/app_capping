"""Histograma antes/después del capping como SVG generado en el servidor (sin JS ni librerías)."""
import math
from xml.sax.saxutils import escape

COLOR_ORIGINAL = "#1F3A5F"
COLOR_CAPEADA = "#C9A227"
CLASES_POR_DECADA = 5


def calcular_clases(originales, capeadas, clases_por_decada: int = CLASES_POR_DECADA) -> dict:
    """Clases en escala log10 comunes a ambas series y sus frecuencias.
    Devuelve {"bordes": [...], "original": [...], "capeada": [...]} (len(bordes) = clases + 1)."""
    originales, capeadas = list(originales), list(capeadas)
    positivos = [v for v in originales + capeadas if v > 0] or [1.0]
    lo = math.floor(math.log10(min(positivos)) + 1e-9)
    hi = math.ceil(math.log10(max(positivos)) - 1e-9)
    if hi <= lo:
        hi = lo + 1
    n = (hi - lo) * clases_por_decada
    bordes = [10 ** (lo + i / clases_por_decada) for i in range(n + 1)]

    def contar(valores):
        cuentas = [0] * n
        for v in valores:
            pos = (math.log10(v) - lo) * clases_por_decada if v > 0 else 0
            cuentas[min(max(int(math.floor(pos + 1e-9)), 0), n - 1)] += 1
        return cuentas

    return {"bordes": bordes, "original": contar(originales), "capeada": contar(capeadas)}


def _fmt(v: float) -> str:
    return f"{v:g}"


def dibujar_svg(clases: dict, umbral: float, titulo: str) -> str:
    """Dibuja el SVG (barras agrupadas, eje X log, línea punteada en el umbral)."""
    W, H = 900, 440
    ml, mr, mt, mb = 60, 20, 50, 70
    pw, ph = W - ml - mr, H - mt - mb
    bordes, orig, cap = clases["bordes"], clases["original"], clases["capeada"]
    n = len(orig)
    lmin, lmax = math.log10(bordes[0]), math.log10(bordes[-1])

    def x_de(v):
        v = min(max(v, bordes[0]), bordes[-1])
        return ml + (math.log10(v) - lmin) / (lmax - lmin) * pw

    ymax = max(max(orig, default=0), max(cap, default=0), 1)
    paso = max(1, math.ceil(ymax / 5))
    ytope = paso * math.ceil(ymax / paso)

    def y_de(c):
        return mt + ph - c / ytope * ph

    t_attr = escape(titulo, {'"': "&quot;"})
    p = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" '
        f'role="img" aria-label="{t_attr}" font-family="Segoe UI, system-ui, sans-serif">',
        f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>',
        f'<text x="{W / 2}" y="26" text-anchor="middle" font-size="16" font-weight="600" '
        f'fill="#1F3A5F">{escape(titulo)}</text>',
    ]
    for t in range(0, ytope + 1, paso):  # eje Y y rejilla
        y = y_de(t)
        p.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{ml + pw}" y2="{y:.1f}" stroke="#E2E8F0"/>')
        p.append(f'<text x="{ml - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="#5A6474">{t}</text>')
    p.append(
        f'<text transform="translate(16 {mt + ph / 2}) rotate(-90)" text-anchor="middle" '
        f'font-size="12" fill="#5A6474">Frecuencia (n.º de muestras)</text>'
    )
    series = ((orig, COLOR_ORIGINAL, "Original"), (cap, COLOR_CAPEADA, "Capeada"))
    for i in range(n):  # barras agrupadas
        x0, x1 = x_de(bordes[i]), x_de(bordes[i + 1])
        ancho = (x1 - x0) * 0.8 / 2
        for k, (cuentas, color, nombre) in enumerate(series):
            c = cuentas[i]
            if c:
                x = x0 + (x1 - x0) * 0.1 + k * ancho
                p.append(
                    f'<rect x="{x:.1f}" y="{y_de(c):.1f}" width="{ancho:.1f}" height="{mt + ph - y_de(c):.1f}" '
                    f'fill="{color}"><title>{nombre}: {c} muestras ({_fmt(bordes[i])} a {_fmt(bordes[i + 1])} g/t)</title></rect>'
                )
    p.append(f'<line x1="{ml}" y1="{mt + ph}" x2="{ml + pw}" y2="{mt + ph}" stroke="#5A6474"/>')
    p.append(f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt + ph}" stroke="#5A6474"/>')
    d = int(round(lmin))
    while d <= lmax + 1e-9:  # etiquetas en décadas
        x = x_de(10 ** d)
        p.append(f'<line x1="{x:.1f}" y1="{mt + ph}" x2="{x:.1f}" y2="{mt + ph + 5}" stroke="#5A6474"/>')
        p.append(f'<text x="{x:.1f}" y="{mt + ph + 20}" text-anchor="middle" font-size="12" fill="#5A6474">{_fmt(10 ** d)}</text>')
        d += 1
    p.append(
        f'<text x="{ml + pw / 2}" y="{H - 28}" text-anchor="middle" font-size="12" fill="#5A6474">'
        f'Ley de Au (g/t, escala logarítmica)</text>'
    )
    xu = x_de(umbral)  # umbral
    p.append(f'<line x1="{xu:.1f}" y1="{mt}" x2="{xu:.1f}" y2="{mt + ph}" stroke="#B91C1C" stroke-width="2" stroke-dasharray="6 4"/>')
    anchor, dx = ("end", -6) if xu > ml + pw * 0.75 else ("start", 6)
    p.append(f'<text x="{xu + dx:.1f}" y="{mt + 14}" text-anchor="{anchor}" font-size="12" font-weight="600" fill="#B91C1C">Umbral {umbral:.2f} g/t</text>')
    for k, (color, nombre) in enumerate(((COLOR_ORIGINAL, "Au original"), (COLOR_CAPEADA, "Au capeada"))):
        x = ml + 10 + k * 120  # leyenda
        p.append(f'<rect x="{x}" y="{H - 14}" width="12" height="12" fill="{color}"/>')
        p.append(f'<text x="{x + 18}" y="{H - 4}" font-size="12" fill="#1A202C">{nombre}</text>')
    p.append("</svg>")
    return "".join(p)


def histograma_svg(originales, capeadas, umbral, zona, etiqueta_metodo, parametro_txt) -> str:
    titulo = f"Au antes y después del capping: {zona}, {etiqueta_metodo} {parametro_txt}"
    return dibujar_svg(calcular_clases(originales, capeadas), umbral, titulo)
