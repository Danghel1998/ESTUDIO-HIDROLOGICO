import io

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import xlsxwriter

from hydro import hyetograph as hy
from hydro import rational, scs

st.set_page_config(page_title="Caudal de Diseño", page_icon="📈", layout="wide")
st.title("📈 Estimación del caudal máximo de diseño")


def _escribir_reporte_informe(wb, cuencas, tabla_scs, tabla_rac, resumen, trs, hietogramas, tramo, situacion, idf_criterio):
    """Genera el reporte de caudales con el mismo formato de cuadros y gráficos
    usado en los estudios de hidrología vial del MTC (título, descripción,
    fórmulas, cuadro con encabezados agrupados, gráficos de hietograma nativos
    de Excel, cuadro del método racional y cuadro resumen final)."""
    n_tr = len(trs)
    nombres = list(cuencas["Nombre"])

    f_title = wb.add_format({"bold": True, "underline": True, "align": "center", "font_size": 13})
    f_desc = wb.add_format({"text_wrap": True, "valign": "top", "font_size": 10})
    f_formula = wb.add_format({"italic": True, "font_size": 10, "valign": "top"})
    f_tramo = wb.add_format({"bold": True, "font_size": 10, "bg_color": "#F2F2F2", "border": 1})
    f_hdr = wb.add_format({"bold": True, "align": "center", "valign": "vcenter", "text_wrap": True,
                            "border": 1, "bg_color": "#D9E1F2", "font_size": 9})
    f_unit = wb.add_format({"italic": True, "align": "center", "valign": "vcenter",
                             "border": 1, "bg_color": "#D9E1F2", "font_size": 8})
    f_cell = wb.add_format({"align": "center", "valign": "vcenter", "border": 1, "font_size": 9})
    f_cell_num = wb.add_format({"align": "center", "valign": "vcenter", "border": 1, "font_size": 9, "num_format": "0.0000"})
    f_cell_q = wb.add_format({"align": "center", "valign": "vcenter", "border": 1, "font_size": 9,
                               "num_format": "0.000", "bold": True})

    ws = wb.add_worksheet("Reporte")
    ws.hide_gridlines(2)
    n_cols_1 = 10 + n_tr
    ws.set_column(0, 0, 12)
    ws.set_column(1, 1, 11)
    ws.set_column(2, 2, 12)
    ws.set_column(3, 9, 10)
    ws.set_column(10, 10 + n_tr - 1, 11)

    row = 0
    ws.merge_range(row, 0, row, n_cols_1 - 1, "CAUDALES HIDROLÓGICOS O DE DISEÑO - MÉTODO DEL NÚMERO DE CURVA DEL SCS", f_title)
    row += 2
    ws.merge_range(row, 0, row + 2, n_cols_1 - 1,
                    "El método del Número de Curva del SCS es aplicable para cuencas menores a 250 km² y con "
                    "limitada información, dando origen a resultados aceptables de caudales punta.\n"
                    "Se obtuvo el caudal de diseño como variable hidrológica para los distintos periodos de "
                    "retorno generado con la aplicación del software HEC-HMS.\n"
                    "Los parámetros sensibles para éste método son el número de curva (obtenido del Mapa de CN) y el Lag time.",
                    f_desc)
    row += 4
    ws.write(row, 0, "Capacidad Potencial Máxima de Retención:", f_formula)
    ws.merge_range(row, 4, row, 6, "S (mm) = 25400/CN - 254", f_formula)
    ws.write(row + 1, 0, "Abstracción inicial:", f_formula)
    ws.merge_range(row + 1, 4, row + 1, 6, "Ia = f * S   (f: entre 0.1 y 0.3)", f_formula)
    ws.write(row + 2, 0, "Tiempo de concentración:", f_formula)
    ws.merge_range(row + 2, 4, row + 2, 6, "LagTime = 0.6*Tc   Tc = 0.3*(L/S^0.25)^0.76", f_formula)
    row += 4

    ws.merge_range(row, 0, row, n_cols_1 - 1, tramo, f_tramo)
    row += 1

    h0, h1, h2 = row, row + 1, row + 2
    ws.merge_range(h0, 0, h2, 0, "CUENCA/\nSUBCUENCA", f_hdr)
    ws.merge_range(h0, 1, h2, 1, "(*) PROG.\nCRUCE DE\nCAUCES", f_hdr)
    ws.merge_range(h0, 2, h2, 2, "HIETOGRAMAS\nDE DISEÑO", f_hdr)
    ws.merge_range(h0, 3, h0, 5, "PARÁM. GEOMORFOLÓGICOS", f_hdr)
    ws.write(h1, 3, "ÁREA (A)", f_hdr)
    ws.write(h1, 4, "LONG. (L)", f_hdr)
    ws.write(h1, 5, "PENDIENTE (S)", f_hdr)
    ws.write(h2, 3, "KM2", f_unit)
    ws.write(h2, 4, "KM", f_unit)
    ws.write(h2, 5, "ML/ML", f_unit)
    ws.merge_range(h0, 6, h2, 6, "N° DE CURVA\nDE ESCORRENTÍA\n(CN)", f_hdr)
    ws.merge_range(h0, 7, h1, 7, "ABSTRAC.\nINICIAL (Ia)", f_hdr)
    ws.write(h2, 7, "MM", f_unit)
    ws.merge_range(h0, 8, h1, 8, "LAG TIME", f_hdr)
    ws.write(h2, 8, "MIN", f_unit)
    ws.merge_range(h0, 9, h2, 9, "MODELAMIENTO\nHIDROLÓGICO", f_hdr)
    ws.merge_range(h0, 10, h0, 10 + n_tr - 1, "RESULTADOS", f_hdr)
    for i, tr in enumerate(trs):
        ws.write(h1, 10 + i, f"CAUDAL MÁX (Q)\nTR={tr:g} AÑOS", f_hdr)
        ws.write(h2, 10 + i, "m3/seg", f_unit)
    row = h2 + 1

    for nom in nombres:
        r_scs = tabla_scs[tabla_scs["Nombre"] == nom].iloc[0]
        r_res = resumen[resumen["Nombre"] == nom].iloc[0]
        ws.write(row, 0, nom, f_cell)
        ws.write(row, 1, str(r_scs["Progresiva"]), f_cell)
        ws.write(row, 2, "Ver hietograma", f_cell)
        ws.write(row, 3, r_scs["Área (km2)"], f_cell_num)
        ws.write(row, 4, r_scs["Long. cauce (km)"], f_cell_num)
        ws.write(row, 5, r_scs["Pendiente S (m/m)"], f_cell_num)
        ws.write(row, 6, r_scs["N° de Curva CN"], f_cell_num)
        ws.write(row, 7, r_scs["Abstrac. inicial Ia (mm)"], f_cell_num)
        ws.write(row, 8, r_scs["Lag time (min)"], f_cell_num)
        ws.write(row, 9, "HEC-HMS / SCS UH", f_cell)
        for i, tr in enumerate(trs):
            ws.write(row, 10 + i, r_res[f"Q máx (Q) - TR={tr} años (m3/s)"], f_cell_q)
        row += 1

    row += 1
    ws.write(row, 0, "(*) Algunos de los cauces se activan sólo en temporadas de fuertes precipitaciones pluviales", f_formula)
    row += 2

    # --- Gráficos de hietograma (nativos de Excel), datos auxiliares fuera de la vista ---
    col_aux = n_cols_1 + 2
    fila_graficos = row
    posiciones = [(fila_graficos, 0), (fila_graficos, 7), (fila_graficos + 17, 3)]
    for i, tr in enumerate(trs[:3]):
        df_t = hietogramas[tr]
        n = len(df_t)
        c0 = col_aux + i * 3
        ws.write(0, c0, f"Duración TR={tr:g}")
        ws.write(0, c0 + 1, f"Precip TR={tr:g}")
        for j in range(n):
            ws.write_number(1 + j, c0, float(df_t["duracion_h"].iloc[j]))
            ws.write_number(1 + j, c0 + 1, float(df_t["hietograma_mm"].iloc[j]))
        pico = float(df_t["hietograma_mm"].max())
        chart = wb.add_chart({"type": "column"})
        chart.add_series({
            "name": f"Hietograma Tr={tr:g} años",
            "categories": [ws.get_name(), 1, c0, n, c0],
            "values": [ws.get_name(), 1, c0 + 1, n, c0 + 1],
            "data_labels": {"value": False},
        })
        chart.set_title({"name": f"HIETOGRAMA DE DISEÑO TR = {tr:g} AÑOS  (Pico: {pico:.2f} mm)"})
        chart.set_x_axis({"name": "Duración (Hr)"})
        chart.set_y_axis({"name": "Precipitación (mm)"})
        chart.set_legend({"none": True})
        chart.set_size({"width": 430, "height": 260})
        rr, cc = posiciones[i]
        ws.insert_chart(rr, cc, chart)

    row = fila_graficos + 17 + 16

    # --- Método Racional ---
    row += 1
    n_cols_2 = 8 + 2 * n_tr
    ws.merge_range(row, 0, row, n_cols_2 - 1, "CAUDALES DE DISEÑO - MÉTODO RACIONAL", f_title)
    row += 2
    ws.write(row, 0, "El modelo matemático del Método Racional es el siguiente:", f_formula)
    ws.merge_range(row, 5, row, 7, "Qmáx = 0.278 · C · I · A  (m3/seg)  — Aplica a cuencas < 10 km²", f_formula)
    row += 1
    ws.write(row, 0, f"(*) I = a·T^b·D^-m — Ecuación de las curvas IDF, criterio {idf_criterio}", f_formula)
    row += 1
    ws.write(row, 0, "Tc = 0.3*(L/S^0.25)^0.76", f_formula)
    row += 2

    hh = row
    ws.merge_range(hh, 0, hh + 1, 0, "CUENCA/\nSUBCUENCA", f_hdr)
    ws.merge_range(hh, 1, hh + 1, 1, "(*) PROG.\nCRUCE DE\nCAUCES", f_hdr)
    ws.merge_range(hh, 2, hh, 4, "PARÁM. GEOMORFOLÓGICOS", f_hdr)
    ws.write(hh + 1, 2, "ÁREA (A) km2", f_hdr)
    ws.write(hh + 1, 3, "LONG. (L) km", f_hdr)
    ws.write(hh + 1, 4, "PENDIENTE (S)", f_hdr)
    ws.merge_range(hh, 5, hh + 1, 5, "TIEMPO DE\nCONCENT. (Tc)\nMIN", f_hdr)
    ws.merge_range(hh, 6, hh, 5 + n_tr, "Imax (mm/h)", f_hdr)
    for i, tr in enumerate(trs):
        ws.write(hh + 1, 6 + i, f"TR={tr:g} años", f_hdr)
    ws.merge_range(hh, 6 + n_tr, hh + 1, 6 + n_tr, "C\nADIMENSIONAL", f_hdr)
    ws.merge_range(hh, 7 + n_tr, hh, 6 + 2 * n_tr, "CAUDAL MÁX (Q)  m3/seg", f_hdr)
    for i, tr in enumerate(trs):
        ws.write(hh + 1, 7 + n_tr + i, f"TR={tr:g} años", f_hdr)
    row = hh + 2

    for nom in nombres:
        r_rac = tabla_rac[tabla_rac["Nombre"] == nom].iloc[0]
        ws.write(row, 0, nom, f_cell)
        ws.write(row, 1, str(r_rac["Progresiva"]), f_cell)
        ws.write(row, 2, r_rac["Área (km2)"], f_cell_num)
        ws.write(row, 3, r_rac["Long. cauce (km)"], f_cell_num)
        ws.write(row, 4, r_rac["Pendiente S (m/m)"], f_cell_num)
        ws.write(row, 5, r_rac["Tc (min)"], f_cell_num)
        for i, tr in enumerate(trs):
            ws.write(row, 6 + i, r_rac[f"Imax - TR={tr} años (mm/h)"], f_cell_num)
        ws.write(row, 6 + n_tr, r_rac["Coef. escorrentía C"], f_cell_num)
        for i, tr in enumerate(trs):
            ws.write(row, 7 + n_tr + i, r_rac[f"Q Racional - TR={tr} años (m3/s)"], f_cell_q)
        row += 1

    row += 2

    # --- Resumen final ---
    ws.merge_range(row, 0, row, 5 + n_tr, "RESUMEN DE CAUDALES DE DISEÑO (Qmáx)", f_title)
    row += 2
    ws.write(row, 0, "Entre los dos métodos (Número de Curva del SCS y Racional), se elige el caudal máximo:", f_formula)
    row += 1

    hh = row
    ws.merge_range(hh, 0, hh + 1, 0, "CUENCA/\nSUBCUENCA", f_hdr)
    ws.merge_range(hh, 1, hh + 1, 1, "(*) PROG.\nCRUCE DE\nCAUCES", f_hdr)
    ws.merge_range(hh, 2, hh, 1 + n_tr, "CAUDAL MÁX (Q)  m3/seg", f_hdr)
    for i, tr in enumerate(trs):
        ws.write(hh + 1, 2 + i, f"TR={tr:g} años", f_hdr)
    ws.merge_range(hh, 2 + n_tr, hh + 1, 2 + n_tr, "OBRA DE\nDRENAJE", f_hdr)
    ws.merge_range(hh, 3 + n_tr, hh + 1, 3 + n_tr, "SITUACIÓN EN\nEL PROYECTO", f_hdr)
    row = hh + 2

    for nom in nombres:
        r_res = resumen[resumen["Nombre"] == nom].iloc[0]
        ws.write(row, 0, nom, f_cell)
        ws.write(row, 1, str(r_res["Progresiva"]), f_cell)
        for i, tr in enumerate(trs):
            ws.write(row, 2 + i, r_res[f"Q máx (Q) - TR={tr} años (m3/s)"], f_cell_q)
        ws.write(row, 2 + n_tr, r_res["Obra de drenaje"], f_cell)
        ws.write(row, 3 + n_tr, situacion, f_cell)
        row += 1

    row += 1
    ws.write(row, 0, "(*) Algunos de los cauces se activan sólo en temporadas de fuertes precipitaciones pluviales", f_formula)
    row += 1
    ws.write(row, 0,
             "(**) En las subcuencas de estudio se proyectan alcantarillas de paso o cruce o badén, por lo que "
             f"solo se empleará el caudal con el menor periodo de retorno calculado (TR={min(trs):g} años).",
             f_formula)

faltantes = []
if "cuencas" not in st.session_state:
    faltantes.append("🗺️ Cuencas (datos topográficos)")
if "intensidad_fn" not in st.session_state:
    faltantes.append("🌧️ Curvas IDF e Hietograma")
if faltantes:
    st.warning("Completa antes: " + ", ".join(faltantes))
    st.stop()

cuencas = st.session_state["cuencas"].copy()
intensidad_fn = st.session_state["intensidad_fn"]
p24h_por_tr = st.session_state.get("p24h_por_tr", {})
periodos_obras = st.session_state.get("periodos_retorno_obras", {})

st.subheader("1. Asignación de periodo de retorno y coeficiente de escorrentía por cuenca")

trs_disponibles = sorted(p24h_por_tr) if p24h_por_tr else [2, 5, 10, 20, 50, 100]

if "Tr asignado" not in cuencas.columns:
    def _match_tr(obra):
        for k, v in periodos_obras.items():
            if str(obra).strip().lower() in k.lower() or k.lower() in str(obra).strip().lower():
                return v
        return trs_disponibles[len(trs_disponibles) // 2] if trs_disponibles else 50
    cuencas["Tr asignado"] = cuencas["Obra de drenaje"].apply(_match_tr)

if "Coef. escorrentía C" not in cuencas.columns:
    cuencas["Coef. escorrentía C"] = 0.50

st.session_state.setdefault("editor_tr_c_version", 0)

tb1, tb2 = st.columns([2, 1])
with tb1:
    tr_bulk = st.number_input(
        "Periodo de retorno T (años) a aplicar a todas las cuencas/subcuencas",
        min_value=1.0, value=float(trs_disponibles[len(trs_disponibles) // 2] if trs_disponibles else 50), step=1.0,
        key="tr_bulk_valor",
    )
with tb2:
    st.write("")
    st.write("")
    if st.button("⬇️ Aplicar T a todas las filas"):
        cuencas["Tr asignado"] = tr_bulk
        st.session_state["cuencas"] = cuencas
        st.session_state["editor_tr_c_version"] += 1
        st.rerun()

cb1, cb2 = st.columns([2, 1])
with cb1:
    cobertura_bulk = st.selectbox(
        "Coeficiente de escorrentía C a aplicar a todas las cuencas/subcuencas",
        list(rational.COEFICIENTES_ESCORRENTIA.keys()),
        key="cobertura_bulk_c",
    )
with cb2:
    st.write("")
    st.write("")
    if st.button("⬇️ Aplicar C a todas las filas"):
        cuencas["Coef. escorrentía C"] = rational.COEFICIENTES_ESCORRENTIA[cobertura_bulk]
        st.session_state["cuencas"] = cuencas
        st.session_state["editor_tr_c_version"] += 1
        st.rerun()

edit_cols = ["Nombre", "Progresiva", "Área (km2)", "Obra de drenaje", "Tr asignado", "Coef. escorrentía C"]
editado = st.data_editor(
    cuencas[edit_cols], use_container_width=True, hide_index=True,
    key=f"editor_tr_c_{st.session_state['editor_tr_c_version']}",
    column_config={
        "Tr asignado": st.column_config.NumberColumn(format="%.0f", min_value=1, step=1),
        "Coef. escorrentía C": st.column_config.NumberColumn(format="%.2f", min_value=0.05, max_value=1.0, step=0.05),
    },
)
cuencas["Tr asignado"] = editado["Tr asignado"]
cuencas["Coef. escorrentía C"] = editado["Coef. escorrentía C"]

with st.expander("Valores de referencia del coeficiente de escorrentía C"):
    st.table(pd.DataFrame(rational.COEFICIENTES_ESCORRENTIA.items(), columns=["Cobertura", "C"]))

metodo_hu = st.radio(
    "Hidrograma unitario (transformación lluvia-escorrentía)",
    ["SCS Adimensional (curvilíneo) — igual que HEC-HMS", "Triangular (Mockus)"],
    horizontal=False,
    help=(
        "HEC-HMS usa por defecto la forma curvilínea real del hidrograma unitario adimensional "
        "del SCS (tabla t/Tp vs Q/Qp del NEH-4), no la simplificación triangular. Ambas comparten "
        "el mismo caudal pico teórico (qp=0.208·A/tp), pero la curvilínea distribuye el volumen de "
        "forma más suave y con una cola más larga (tb=5·tp en vez de 2.67·tp), igual que HEC-HMS."
    ),
)
fia1, fia2 = st.columns([3, 1])
with fia2:
    manual_ia = st.checkbox("Ingresar f manualmente")
with fia1:
    if manual_ia:
        factor_ia = st.number_input(
            "Factor de abstracción inicial Ia = f·S (SCS)",
            min_value=0.01, max_value=1.0, value=0.20, step=0.001, format="%.4f",
            help="Ia y la lluvia efectiva de la tabla se recalculan multiplicando S por este f.",
        )
    else:
        factor_ia = st.slider("Factor de abstracción inicial Ia = f·S (SCS)", 0.10, 0.30, 0.20, 0.01)
c_cal1, c_cal2 = st.columns(2)
with c_cal1:
    cn_calibracion = st.slider(
        "CN usado para las pérdidas (calibración de volumen vs. HEC-HMS)", 30.0, 98.0, 0.0, 1.0,
        help=(
            "Déjalo en 0 para usar el CN reportado de cada cuenca (columna N° de Curva CN) tal cual. "
            "Si tienes el Volumen (mm) de una corrida real de HEC-HMS (Global Summary Results) y no "
            "coincide con el 'Volumen escorrentía (mm)' de esta página, puedes fijar aquí un CN de "
            "cálculo distinto (normalmente más bajo) para calibrar el volumen sin alterar el CN que "
            "reportas como dato de entrada de la cuenca."
        ),
    )
with c_cal2:
    factor_lag = st.slider(
        "Factor de calibración del Lag Time (× 0.6·Tc, calibración de Qmax vs. HEC-HMS)", 0.5, 10.0, 1.0, 0.1,
        help=(
            "En HEC-HMS el 'Lag' del método de transformación SCS Unit Hydrograph es un parámetro "
            "libre que el modelador puede editar/calibrar; no siempre coincide con 0.6·Tc calculado "
            "por fórmula. Déjalo en 1.0 para usar 0.6·Tc tal cual. Si tienes el Peak Discharge real de "
            "HEC-HMS y no coincide con el Qmax de esta página (incluso con el volumen ya calibrado), "
            "sube este factor: un Lag Time mayor atenúa y retrasa el pico, igual que ocurre en una "
            "corrida real con tránsito/routing entre elementos."
        ),
    )
trs_defecto_calculo = sorted(set(periodos_obras.values())) or [71, 100, 140]
trs_calculo = st.multiselect(
    "Periodos de retorno T (años) a calcular para todas las cuencas/subcuencas",
    sorted(set(trs_disponibles) | set(trs_defecto_calculo)),
    default=trs_defecto_calculo,
)

metodo_tormenta = st.radio(
    "Método de generación de la tormenta de diseño",
    ["Bloque alterno (Ven Te Chow) — a partir de las curvas IDF",
     "SCS Tipo II 24h (NRCS) — igual que 'Hypothetical Storm' de HEC-HMS"],
    horizontal=False,
    help=(
        "El 'Hypothetical Storm' de HEC-HMS (Method: SCS Type 2) NO usa el bloque alterno: reparte "
        "una lámina puntual de 24h ('Point Depth') según la distribución adimensional SCS Tipo II del "
        "NRCS (National Engineering Handbook, Cap. 4), con un pico muy concentrado (≈43% de la lámina "
        "cae en la hora pico). El 'Point Depth' es la Pmax24h de tu análisis de frecuencias para ese T "
        "(no el total del hietograma IDF, que puede extrapolar la ecuación de Bell/Dyck-Peschke más "
        "allá de su rango válido)."
    ),
)
usar_scs_tipo_ii = metodo_tormenta.startswith("SCS Tipo II")

point_depth_por_tr = {}
if usar_scs_tipo_ii:
    st.caption(
        "Profundidad puntual de 24h ('Point Depth') por periodo de retorno, tomada de "
        "📊 Análisis de Frecuencias. Edítala si tu proyecto de HEC-HMS usa un valor distinto."
    )
    trs_ref = sorted(p24h_por_tr) if p24h_por_tr else []
    cols_pd = st.columns(min(len(trs_calculo), 4) or 1)
    for i, tr in enumerate(trs_calculo):
        default_pd = float(p24h_por_tr.get(tr, np.interp(tr, trs_ref, [p24h_por_tr[t] for t in trs_ref]))) if trs_ref else 100.0
        with cols_pd[i % len(cols_pd)]:
            point_depth_por_tr[tr] = st.number_input(
                f"Point Depth TR={tr:g} (mm)", min_value=1.0, value=round(default_pd, 2), step=0.1,
                key=f"point_depth_{tr}",
            )

dt_h_calc = st.number_input("Intervalo Δt del hietograma de diseño (h)", 0.0833, 6.0, 1.0, step=0.25, disabled=usar_scs_tipo_ii)
dur_total_h = st.number_input("Duración total de la tormenta de diseño (h)", 1.0, 48.0, 24.0, step=1.0, disabled=usar_scs_tipo_ii)
paso_calculo_h = st.number_input(
    "Paso de cómputo interno (h) — igual que el 'Time Interval' de las Control Specifications de HEC-HMS",
    0.0167, dt_h_calc, min(0.1667, dt_h_calc), step=0.0167, format="%.4f",
    help=(
        "HEC-HMS no convoluciona con el mismo Δt grueso del hietograma de diseño: internamente usa "
        "un paso de cómputo más fino (típicamente 5-15 min), repartiendo la lámina de cada bloque "
        "en pasos de igual intensidad. Esto afina el pico real del hidrograma unitario en vez de la "
        "aproximación en bloques de 1h. Déjalo igual al Δt de arriba para replicar el cálculo simple."
    ),
)
st.caption(
    "⚠️ En cuencas pequeñas y de respuesta rápida (Tc de pocas horas), usar una tormenta de "
    "24h completas sobreestima mucho el caudal SCS, porque casi toda la lluvia acumulada del "
    "día termina contando como escorrentía efectiva. Es habitual usar una duración de tormenta "
    "del orden de 1 a 4 veces el Tc de la cuenca más exigente; ajusta este valor y compara la "
    "sensibilidad del resultado."
)

st.markdown("###### Datos previos por cuenca/subcuenca")
datos_previos = {}
for _, row in cuencas.iterrows():
    tc_h = row["Tc adoptado (h)"]
    cn = row["N° de Curva CN"]
    s_mm = scs.retencion_potencial_mm(cn)
    ia_mm = scs.abstraccion_inicial_mm(s_mm, factor_ia)
    datos_previos[row["Nombre"]] = {
        "L (long. cauce, km)=": round(row["Long. cauce principal (km)"], 4),
        "S (pendiente del cauce, m/m)=": round(row["Pendiente S (m/m)"], 4),
        "Tc (h)=": round(tc_h, 7),
        "Tc (min)=": round(tc_h * 60, 6),
        "Lag time (min)=": round(0.6 * tc_h * 60, 6),
        "S (retención SCS, mm)=": round(s_mm, 6),
        "Ia (abstracción inicial, mm)=": round(ia_mm, 7),
    }
st.dataframe(pd.DataFrame(datos_previos), use_container_width=True)
st.caption(
    "⚠️ Ojo: hay dos variables distintas llamadas 'S' en hidrología. La **S de pendiente del "
    "cauce (m/m)** es la que entra en las fórmulas de Tc (Kirpich, Bransby-Williams, US Corps, "
    "etc.). La **S de retención potencial SCS (mm)** = 25400/CN − 254 es otra cosa: solo se usa "
    "para Ia y las pérdidas del método del Número de Curva, no interviene en el cálculo de Tc."
)

st.divider()
if st.button("🧮 Calcular caudales de diseño", type="primary") and trs_calculo:
    hietogramas_calc = dict(st.session_state.get("hietogramas", {}))
    filas_scs, filas_rac, filas_resumen = [], [], []
    series_hidrograma = {}
    avisos_paso_calculo = []

    for _, row in cuencas.iterrows():
        area = row["Área (km2)"]
        tc_h = row["Tc adoptado (h)"]
        cn = row["N° de Curva CN"]
        cn_perdidas = cn_calibracion if cn_calibracion > 0 else cn
        c = row["Coef. escorrentía C"]
        s_mm = scs.retencion_potencial_mm(cn)
        ia_mm = scs.abstraccion_inicial_mm(s_mm, factor_ia)
        lag_time_min = 0.6 * tc_h * 60.0
        lag_calibrado_h = factor_lag * 0.6 * tc_h

        # HEC-HMS exige que el intervalo de simulación sea <= 0.29 * Lag time
        # (Advertencia 41784: "Simulation time interval is greater than 0.29 *
        # lag for subbasin ..."); replicamos exactamente esa misma validación.
        limite_paso_h = 0.29 * (lag_calibrado_h * 60.0) / 60.0
        if paso_calculo_h > limite_paso_h:
            avisos_paso_calculo.append(
                f"⚠️ Paso de cómputo ({paso_calculo_h*60:.1f} min) mayor que 0.29·Lag para "
                f"'{row['Nombre']}' (Lag={lag_calibrado_h*60:.2f} min → máximo permitido "
                f"{limite_paso_h*60:.2f} min); reduce el paso de cómputo."
            )

        tp_h = dt_h_calc / 2.0 + lag_calibrado_h
        qp_unitario = 0.208 * area / tp_h if tp_h > 0 else 0.0

        fila_scs = {"Nombre": row["Nombre"], "Progresiva": row["Progresiva"], "Área (km2)": round(area, 4),
                    "Long. cauce (km)": round(row["Long. cauce principal (km)"], 3),
                    "Pendiente S (m/m)": round(row["Pendiente S (m/m)"], 4), "N° de Curva CN": cn,
                    "Abstrac. inicial Ia (mm)": round(ia_mm, 4), "Lag time (min)": round(lag_time_min, 3),
                    "Lag time calibrado (min)": round(lag_calibrado_h * 60.0, 3),
                    "Tp (h)": round(tp_h, 4), "Qp unitario (m3/s por mm)": round(qp_unitario, 4)}
        fila_rac = {"Nombre": row["Nombre"], "Progresiva": row["Progresiva"], "Área (km2)": round(area, 4),
                    "Long. cauce (km)": round(row["Long. cauce principal (km)"], 3),
                    "Pendiente S (m/m)": round(row["Pendiente S (m/m)"], 4), "Tc (min)": round(tc_h * 60, 3),
                    "Coef. escorrentía C": c}
        q_por_tr = {}

        for tr in trs_calculo:
            if usar_scs_tipo_ii:
                clave_cache = f"scsII_{tr}_{point_depth_por_tr.get(tr)}_{paso_calculo_h}"
                if clave_cache in hietogramas_calc:
                    df_h = hietogramas_calc[clave_cache]
                else:
                    df_h = hy.scs_tipo_ii_24h(point_depth_por_tr[tr], paso_calculo_h)
                    hietogramas_calc[clave_cache] = df_h
                    hietogramas_calc[tr] = df_h
                hietograma_calc_mm = df_h["hietograma_mm"].to_numpy()
                dt_real = float(df_h["duracion_h"].iloc[0])
            else:
                if tr in hietogramas_calc:
                    df_h = hietogramas_calc[tr]
                else:
                    df_h = hy.bloque_alterno(intensidad_fn, tr, dur_total_h, dt_h_calc)
                    hietogramas_calc[tr] = df_h
                dt_real = float(df_h["duracion_h"].iloc[0])

                if paso_calculo_h < dt_real - 1e-9:
                    df_fino = hy.refinar_hietograma(df_h, paso_calculo_h)
                    hietograma_calc_mm = df_fino["hietograma_mm"].to_numpy()
                    dt_real = float(df_fino["duracion_h"].iloc[0])
                else:
                    hietograma_calc_mm = df_h["hietograma_mm"].to_numpy()

            pe = scs.hietograma_efectivo(hietograma_calc_mm, cn_perdidas, factor_ia)
            if metodo_hu.startswith("Triangular"):
                hu = scs.hidrograma_unitario_triangular(area, tc_h, dt_real, lag_override_h=lag_calibrado_h)
            else:
                hu = scs.hidrograma_unitario_scs_adimensional(area, tc_h, dt_real, lag_override_h=lag_calibrado_h)
            hcre = scs.hidrograma_creciente(pe, hu, dt_real)
            q_scs = hcre["q_max"]
            t_pico_h = float(hcre["t_h"][np.argmax(hcre["q_m3s"])]) if len(hcre["q_m3s"]) else 0.0
            fila_scs[f"Q SCS - TR={tr} años (m3/s)"] = round(q_scs, 3)
            fila_scs[f"Volumen escorrentía - TR={tr} años (mm)"] = round(float(pe.sum()), 2)
            fila_scs[f"Tiempo al pico - TR={tr} años (h)"] = round(t_pico_h, 2)

            series_hidrograma[(row["Nombre"], tr)] = {
                "t_h": hcre["t_h"], "q_m3s": hcre["q_m3s"],
                "pe_mm": pe, "hu": hu, "dt_h": dt_real,
            }

            tc_min = tc_h * 60.0
            i_tc = intensidad_fn(tr, tc_min)
            q_rac = rational.metodo_racional(c, i_tc, area)
            fila_rac[f"Imax - TR={tr} años (mm/h)"] = round(i_tc, 2)
            fila_rac[f"Q Racional - TR={tr} años (m3/s)"] = round(q_rac, 3)

            q_por_tr[tr] = (q_scs, q_rac)

        filas_scs.append(fila_scs)
        filas_rac.append(fila_rac)

        fila_resumen = {"Nombre": row["Nombre"], "Progresiva": row["Progresiva"], "Obra de drenaje": row["Obra de drenaje"]}
        for tr in trs_calculo:
            q_scs, q_rac = q_por_tr[tr]
            fila_resumen[f"Q máx (Q) - TR={tr} años (m3/s)"] = round(max(q_scs, q_rac), 3)
        filas_resumen.append(fila_resumen)

    st.session_state["hietogramas"] = hietogramas_calc
    st.session_state["tabla_scs"] = pd.DataFrame(filas_scs)
    st.session_state["tabla_racional"] = pd.DataFrame(filas_rac)
    st.session_state["resumen_caudales"] = pd.DataFrame(filas_resumen)
    st.session_state["trs_calculo_usados"] = trs_calculo
    st.session_state["series_hidrograma"] = series_hidrograma
    st.session_state["avisos_paso_calculo"] = sorted(set(avisos_paso_calculo))

if "resumen_caudales" in st.session_state:
    trs_usados = st.session_state["trs_calculo_usados"]

    avisos_paso = st.session_state.get("avisos_paso_calculo", [])
    if avisos_paso:
        st.warning(
            "**HEC-HMS exige que el paso de cómputo sea ≤ 0.29 × Lag time** (mismo criterio de la "
            "Advertencia 41784: *'Simulation time interval is greater than 0.29 \\* lag'*). "
            "Con el paso de cómputo actual esto se incumple en:\n\n" + "\n".join(f"- {a}" for a in avisos_paso)
        )

    st.subheader("2. Caudales hidrológicos o de diseño — Método del Número de Curva del SCS")
    st.caption(
        "El método del Número de Curva del SCS es aplicable para cuencas menores a 250 km² y con "
        "limitada información, dando origen a resultados aceptables de caudales punta. Los parámetros "
        "sensibles para este método son el número de curva y el Lag time."
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        st.latex(r"S_{(mm)} = \dfrac{25400}{CN} - 254")
    with c2:
        st.latex(r"I_a = f \cdot S \quad (f: 0.1\text{ a }0.3)")
    with c3:
        st.latex(r"LagTime = 0.6 \cdot T_c \qquad T_c = 0.3\left(\dfrac{L}{S^{0.25}}\right)^{0.76}")

    st.markdown("**Transformación lluvia-escorrentía — Hidrograma Unitario SCS (igual que HEC-HMS)**")
    st.caption(
        "Fuente: HEC-HMS Technical Reference Manual — 'SCS Unit Hydrograph Model' "
        "(hec.usace.army.mil/confluence/hmsdocs/hmstrm/transform/scs-unit-hydrograph-model)."
    )
    d1, d2, d3 = st.columns(3)
    with d1:
        st.latex(r"T_p = \dfrac{t_r}{2} + LagTime")
        st.caption(r"$t_r$: intervalo Δt del hietograma")
    with d2:
        st.latex(r"Q_p = \dfrac{PRF \cdot A}{T_p}")
        st.caption("PRF = 484 (unid. inglesas) → 0.208 en unidades métricas (A: km², Tp: h, Qp: m³/s por mm)")
    with d3:
        st.latex(r"Q_{max} = \sum \big(Pe_i \cdot Q_p(t - t_i)\big)")
        st.caption("Convolución del hidrograma unitario con la lluvia efectiva incremental")
    st.dataframe(st.session_state["tabla_scs"], use_container_width=True, hide_index=True)
    st.caption(
        "💡 La columna **Volumen escorrentía (mm)** es la lámina total de lluvia efectiva "
        "(equivalente al 'Volume (MM)' del Global Summary Results de HEC-HMS) y **Q SCS** es "
        "equivalente al 'Peak Discharge'. Si tienes una corrida real de HEC-HMS para comparar: "
        "primero ajusta **'CN usado para las pérdidas'** hasta que el Volumen coincida, y luego "
        "ajusta el **'Factor de calibración del Lag Time'** hasta que el Qmax coincida — así se "
        "calibra un modelo SCS igual que se calibraría el .basin real de HEC-HMS, sin tocar el CN "
        "ni el Tc que reportas como dato de entrada de la cuenca."
    )

    st.subheader("3. Caudales de diseño — Método Racional")
    st.latex(r"Q = 0.278 \cdot C \cdot I \cdot A \quad (m^3/s) \qquad \text{Aplica a cuencas} < 10\,km^2")
    st.dataframe(st.session_state["tabla_racional"], use_container_width=True, hide_index=True)

    st.subheader("4. Resumen de caudales de diseño")
    st.caption("Entre los dos métodos (Número de Curva del SCS y Racional), se elige el caudal máximo (Qmáx).")
    resumen = st.session_state["resumen_caudales"]
    st.dataframe(resumen, use_container_width=True, hide_index=True)

    fig = go.Figure()
    for tr in trs_usados:
        fig.add_trace(go.Bar(x=resumen["Nombre"], y=resumen[f"Q máx (Q) - TR={tr} años (m3/s)"], name=f"TR={tr} años"))
    fig.update_layout(barmode="group", yaxis_title="Caudal (m3/s)", title="Caudal máximo de diseño por cuenca y periodo de retorno")
    st.plotly_chart(fig, use_container_width=True)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        st.session_state["tabla_scs"].to_excel(writer, index=False, sheet_name="Metodo SCS")
        st.session_state["tabla_racional"].to_excel(writer, index=False, sheet_name="Metodo Racional")
        resumen.to_excel(writer, index=False, sheet_name="Resumen Caudales")
        if "cuencas" in st.session_state:
            st.session_state["cuencas"].to_excel(writer, index=False, sheet_name="Cuencas")
        if "station_data" in st.session_state:
            st.session_state["station_data"].to_excel(writer, index=False, sheet_name="Estacion")
    st.download_button(
        "⬇️ Descargar resumen en Excel", buffer.getvalue(),
        file_name="resumen_caudales_diseno.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.divider()
    st.subheader("5. Reporte final (formato informe de hidrología)")
    st.caption("Genera el reporte con el mismo formato de cuadros y gráficos usado en los estudios de hidrología vial del MTC.")
    rc1, rc2 = st.columns(2)
    with rc1:
        nombre_tramo = st.text_input("Tramo (encabezado de las tablas)", "TRAMO: EMP PE-5NC (SAN ANTONIO) – EL PORVENIR")
    with rc2:
        situacion_proyecto = st.text_input("Situación en el proyecto (todas las cuencas)", "Proyectada")

    if st.button("📄 Generar reporte final"):
        tabla_scs = st.session_state["tabla_scs"]
        tabla_rac = st.session_state["tabla_racional"]
        modelo_idf = st.session_state.get("idf_criterio", "Frederic Bell")
        hietogramas_rep = dict(st.session_state.get("hietogramas", {}))
        for tr in trs_usados:
            if tr not in hietogramas_rep:
                hietogramas_rep[tr] = hy.bloque_alterno(intensidad_fn, tr, dur_total_h, dt_h_calc)

        buffer2 = io.BytesIO()
        with xlsxwriter.Workbook(buffer2, {"in_memory": True}) as wb:
            _escribir_reporte_informe(
                wb, cuencas, tabla_scs, tabla_rac, resumen, trs_usados,
                hietogramas_rep, nombre_tramo, situacion_proyecto, modelo_idf,
            )
        st.session_state["reporte_informe_excel"] = buffer2.getvalue()

    if "reporte_informe_excel" in st.session_state:
        st.download_button(
            "⬇️ Descargar reporte final (Excel, formato informe)", st.session_state["reporte_informe_excel"],
            file_name="reporte_caudales_diseno.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    st.success("Caudal máximo de diseño calculado para todas las cuencas/subcuencas.")

st.sidebar.divider()
st.sidebar.caption("HIDROPro v1.0 · Creado por el Ing. Daniel Oliden")
