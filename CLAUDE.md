# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Problema
Sun Valley explora el Proyecto Aurora (oro): Veta Norte y Veta Sur. Antes de estimar recursos, el geólogo detecta
outliers (efecto pepita) y aplica capping, porque pocas muestras muy altas inflan la ley media. Hoy lo hace a mano
en Excel. La app `capping_web` carga los datos, valida inconsistencias, calcula el capping y el geólogo decide.

## Insumos (solo lectura, nunca modificarlos)
La carpeta en disco se llama `Insumos/` (con mayúscula; Windows no distingue mayúsculas, pero úsala así en el código).
Cada Excel tiene una sola hoja (`Sheet1`) con fila de encabezado; los nombres de columna se conservan en español.
- `insumos/Maestro_Sondajes.xlsx`: Sondaje_ID, Zona, Este_m, Norte_m, Elevacion_m, Azimut_grados,
  Buzamiento_grados, Profundidad_m, Fecha_Finalizacion
  - 12 sondajes (DDH-001…DDH-012). `Zona` ∈ {Veta Norte, Veta Sur}. `Buzamiento_grados` negativo = hacia abajo.
    `Fecha_Finalizacion` viene como fecha de Excel.
- `insumos/Resultados_Laboratorio.xlsx`: Muestra_ID, Sondaje_ID, Desde_m, Hasta_m, Au_gpt, Lote_Laboratorio
  - 176 filas (M-4001…M-4176). `Au_gpt` en g/t.
- La llave entre ambos es `Sondaje_ID`; la zona de cada muestra viene del maestro.

## Reglas del negocio
- **R1** Muestra cuyo Sondaje_ID no existe en el maestro → se excluye y se reporta como inconsistencia.
- **R2** Sondaje del maestro sin muestras → se reporta como inconsistencia.
- **R3** Au_gpt = -99 (bajo límite de detección) → 0.01; se guarda también el valor original.
- **R4** Método Percentil: umbral = percentil P (90, 95, 97.5, 99; defecto 95), igual a PERCENTILE.INC de Excel
  (interpolación lineal; equivale a `numpy.percentile(..., method="linear")`).
- **R5** Método Media + k·σ: umbral = media + k × desviación estándar muestral (k = 2, 2.5, 3; defecto 2),
  igual a STDEV.S (ddof = 1).
- **R6** Outlier = Au_gpt estrictamente mayor que el umbral; Au_capped = min(Au_gpt, umbral).
- **R7** Nunca modificar la ley original. Filtro por zona: Todas, Veta Norte, Veta Sur; el umbral se calcula con
  las muestras válidas de la zona elegida.

## Cifras de control (zona Todas)
- 174 muestras válidas; media 3.55; mediana 1.355; máximo 95.40 (M-4026, DDH-002).
- Percentil 95: umbral 8.36; 9 outliers; media capeada 2.23 (−37.3 %).
- Media + 2σ: umbral 22.09; 6 outliers; media capeada 2.76.
- Veta Norte P95: 122 muestras, umbral 8.83, 7 outliers, media capeada 2.52.
- Veta Sur P95: 52 muestras, umbral 6.02, 3 outliers, media capeada 1.47.
- Inconsistencias: M-4175 y M-4176 (DDH-099, R1) y DDH-012 (R2).
- Tolerancia ±0.01 en leyes y umbrales; conteos exactos.

## Arquitectura (obligatoria)
- MVC con Flask:
  - `app/models`: modelos SQLAlchemy.
  - `app/controllers`: Blueprints, sin lógica de negocio. Se registran dentro de `create_app`.
  - `app/templates`: Jinja; todas extienden `base.html` (azul `#1F3A5F`, dorado `#C9A227`).
  - `app/services`: la lógica.
- `app/__init__.py` contiene la fábrica `create_app(test_config=None)`. `app/extensions.py` contiene el
  `db = SQLAlchemy()` compartido. `run.py` arranca en http://127.0.0.1:5000 con debug.
- SQLite (`instance/capping.db`) con Flask-SQLAlchemy. Tablas: Sondaje, Muestra (au_original y au_gpt),
  Inconsistencia. Al arrancar se reconstruye la BD desde `insumos/`.
- `app/services/carga.py`: lee los Excel y aplica R1 a R3.
- `app/services/capping.py`: R4 a R7 como funciones puras (reciben una lista de leyes; sin Flask ni BD).
- `app/services/exportar.py`: genera Leyes_Capeadas.xlsx.
- Tests en `tests/`:
  - Usan los Excel de `insumos/` y comprueban las cifras de control.
  - Fixtures `app` y `client` en `tests/conftest.py`, con SQLite temporal en `tmp_path` e `INSUMOS_DIR` real.
  - `pythonpath = ["."]` en pyproject permite importar `app`. El proyecto no se empaqueta: no tiene build-system.

## Convenciones
- Todo con uv (nunca pip): `uv add <pkg>`, `uv add --dev <pkg>`, `uv sync`.
- Nunca modificar `insumos/`.
- Commits pequeños en español; nunca subir `.venv`, `instance/` ni `*.db`.
- Comandos (los ejecuta Claude):
  - `uv run run.py`: servidor de desarrollo.
  - `uv run pytest`: todos los tests.
  - `uv run pytest tests/test_home.py::test_home_muestra_titulo`: un solo test.

## Entorno
- Windows, sin Python del sistema: usar siempre `uv run`. uv está en `~/.local/bin`; en una terminal nueva puede
  hacer falta agregarlo al `PATH`.
- La carpeta está en OneDrive: no generar archivos temporales grandes dentro del proyecto.
