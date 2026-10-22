import logging

from flask import (Blueprint, abort, current_app, flash, redirect, render_template, request,
                   send_file, url_for)

from app.services import capping, consultas, exportar, histograma

main_bp = Blueprint("main", __name__)

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _filtros(origen):
    try:
        return consultas.leer_filtros(origen.get("zona"), origen.get("metodo"), origen.get("parametro"))
    except ValueError as error:
        abort(400, description=str(error))


@main_bp.route("/")
def index():
    zona, metodo, parametro = _filtros(request.args)
    datos = consultas.analisis(zona, metodo, parametro)
    svg = histograma.histograma_svg(
        datos["originales"], datos["capeadas"], datos["resumen"]["umbral"], zona,
        consultas.ETIQUETAS_METODO[metodo], consultas.etiqueta_parametro(metodo, parametro),
    )
    return render_template(
        "index.html",
        contadores=consultas.contadores(),
        inconsistencias=consultas.listar_inconsistencias(),
        filtros={"zona": zona, "metodo": metodo, "parametro": parametro},
        zonas=consultas.ZONAS,
        metodos=consultas.ETIQUETAS_METODO,
        parametros=capping.PARAMETROS,
        histograma_svg=svg,
        **datos,
    )


@main_bp.route("/exportar")
def exportar_excel():
    zona, metodo, parametro = _filtros(request.args)
    return send_file(
        exportar.generar_excel(zona, metodo, parametro),
        as_attachment=True,
        download_name="Leyes_Capeadas.xlsx",
        mimetype=XLSX,
    )


@main_bp.route("/recargar", methods=["POST"])
def recargar():
    zona, metodo, parametro = _filtros(request.form)
    try:
        flash(consultas.recargar_datos(current_app.config["INSUMOS_DIR"]), "ok")
    except Exception as error:
        logging.getLogger(__name__).exception("Falló la recarga de datos")
        flash(f"No se pudo recargar los datos: {error}", "error")
    return redirect(url_for("main.index", zona=zona, metodo=metodo, parametro=parametro))


@main_bp.app_errorhandler(400)
def solicitud_invalida(error):
    return render_template("error400.html", mensaje=error.description), 400
