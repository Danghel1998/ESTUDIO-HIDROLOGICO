import io

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from hydro import hyetograph as hy
from hydro import idf

st.set_page_config(page_title="Curvas IDF e Hietograma", page_icon="🌧️", layout="wide")
st.title("🌧️ Curvas Intensidad-Duración-Frecuencia e Hietograma de diseño")

if "p24h_por_tr" not in st.session_state:
    st.warning("Primero completa **📊 Análisis de frecuencias** para obtener Pmax24h por periodo de retorno.")
    st.stop()

p24h_por_tr = st.session_state["p24h_por_tr"]
trs_ref = sorted(p24h_por_tr)

st.subheader("1. Cálculo de intensidad máxima")

duraciones_min = st.multiselect(
    "Duraciones a evaluar (minutos)",
    idf.DURACIONES_MIN_DEFAULT + [15, 45, 90, 100, 140, 200],
    default=[20, 30, 60, 120, 180, 240],
)
duraciones_min = sorted(set(duraciones_min))


def _p24h_lookup(t):
    return p24h_por_tr[t] if t in p24h_por_tr else float(np.interp(t, trs_ref, [p24h_por_tr[k] for k in trs_ref]))


def _tabla_calculo(base_fn, trs, duraciones):
    data_min = {"T": trs, "PT24h": [round(_p24h_lookup(t), 2) for t in trs]}
    for d in duraciones:
        data_min[f"{d:.2f}"] = [round(base_fn(t, d), 2) for t in trs]
    data_h = {"T": trs, "PT24h": [round(_p24h_lookup(t), 2) for t in trs]}
    for d in duraciones:
        data_h[f"{d / 60:.2f}"] = [round(base_fn(t, d), 2) for t in trs]
    return pd.DataFrame(data_min), pd.DataFrame(data_h)


DURACIONES_IMAX = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120]


def _tabla_imax(modelo, trs_sel):
    data = {"Duración D": DURACIONES_IMAX}
    for t in trs_sel:
        data[f"T = {t} años"] = [round(modelo["intensidad_fn"](t, d), 2) for d in DURACIONES_IMAX]
    return pd.DataFrame(data)


def _bloque_calculo(nombre, base_fn, modelo, trs, duraciones):
    st.markdown(f"##### Cálculo de intensidad máxima con el criterio de {nombre}")
    tabla_min, tabla_h = _tabla_calculo(base_fn, trs, duraciones)
    st.caption("Duración (Minutos)")
    st.dataframe(tabla_min, use_container_width=True, hide_index=True)
    st.caption("Duración (horas)")
    st.dataframe(tabla_h, use_container_width=True, hide_index=True)

    st.markdown("**Ajuste**")
    st.latex(f"I_{{max}} = {modelo['a']:.4f} \\cdot T^{{{modelo['b']:.4f}}} \\cdot D^{{-{modelo['m']:.4f}}}")
    ca, cb, cc = st.columns(3)
    ca.metric("R", f"{modelo['r']:.4f}")
    cb.metric("R²", f"{modelo['r2']:.4f}")
    cc.metric("Se", f"{modelo['se']:.4f}")

    # La ecuación ajustada acepta cualquier T, no solo el set usado para calibrar;
    # se ofrecen como opciones los T de diseño más los estándar 5/10/20/50.
    opciones_trs = sorted(set(trs_ref) | set(trs) | {5, 10, 20, 50})
    trs_defecto = [t for t in [5, 10, 20, 50] if t in opciones_trs]
    trs_sel = st.multiselect(
        f"Periodos de retorno para la tabla de Imax ({nombre})", opciones_trs,
        default=trs_defecto,
        key=f"trs_imax_{nombre}",
    )
    if trs_sel:
        st.caption(f"Valores de Imax, para diferentes D en min y para T = {', '.join(map(str, trs_sel))} años")
        st.dataframe(_tabla_imax(modelo, trs_sel), use_container_width=True, hide_index=True)
    return trs_sel


tab_dp, tab_bell = st.tabs(["📐 Criterio Dyck y Peschke", "📐 Criterio Frederic Bell"])

with tab_dp:
    base_dp = lambda t, d: idf.dyck_peschke_intensidad(_p24h_lookup(t), d)
    modelo_dp = idf.ajustar_regresion_idf(p24h_por_tr, duraciones_min)
    trs_sel_dp = _bloque_calculo("Dick Peschke", base_dp, modelo_dp, trs_ref, duraciones_min)

with tab_bell:
    p24h_t10 = _p24h_lookup(10)
    base_bell = idf.frederic_bell_intensidad_fn(p24h_t10)
    modelo_bell = idf.ajustar_regresion_bell(p24h_por_tr)
    st.caption(
        f"P₁,₁₀ (precipitación de 1h, T=10 años, estimada por Dyck-Peschke) = {idf.frederic_bell_p110(p24h_t10):.2f} mm. "
        "El ajuste de Bell usa el set fijo estándar de T (2,3,5,10,25,50,100 años) y duraciones "
        "(5,10,20,30,60,120 min) de Hidroesta, independiente de los T de diseño elegidos arriba."
    )
    trs_sel_bell = _bloque_calculo("Frederic Bell", base_bell, modelo_bell, idf.BELL_TRS_ESTANDAR, idf.BELL_DURACIONES_ESTANDAR)

st.divider()
st.markdown("###### Selección del criterio para las curvas IDF y el hietograma de diseño")
mejor_criterio = "Dyck y Peschke" if modelo_dp["r2"] >= modelo_bell["r2"] else "Frederic Bell"
criterio = st.radio(
    "Ecuación a usar en los siguientes pasos",
    ["Dyck y Peschke", "Frederic Bell"],
    index=["Dyck y Peschke", "Frederic Bell"].index(mejor_criterio),
    horizontal=True,
    help="El Manual MTC recomienda usar el criterio con mejor coeficiente de determinación (R²).",
)
modelo_elegido = modelo_dp if criterio == "Dyck y Peschke" else modelo_bell
trs_curva = trs_sel_dp if criterio == "Dyck y Peschke" else trs_sel_bell
intensidad_fn = modelo_elegido["intensidad_fn"]
st.caption(
    f"Usando **{criterio}** (R² = {modelo_elegido['r2']:.4f}): "
    f"I = {modelo_elegido['a']:.4f} · T^{modelo_elegido['b']:.4f} · D^-{modelo_elegido['m']:.4f}"
)

st.session_state["intensidad_fn"] = intensidad_fn
st.session_state["idf_criterio"] = criterio
st.session_state["idf_abm"] = {"a": modelo_elegido["a"], "b": modelo_elegido["b"], "m": modelo_elegido["m"]}

st.divider()
st.subheader("2. Curvas Intensidad-Duración-Frecuencia")
st.caption(
    "La curva se traza a partir de la misma tabla 'Valores de Imax' calculada arriba para el "
    "criterio elegido (mismos T y duraciones D en min)."
)

if not trs_curva:
    st.warning("Selecciona al menos un periodo de retorno en la tabla de Imax del criterio elegido para graficar la curva.")
    st.stop()

filas = []
for tr in trs_curva:
    for d in DURACIONES_IMAX:
        filas.append({"T (años)": tr, "Duración (min)": d, "Intensidad (mm/h)": round(intensidad_fn(tr, d), 2)})
df_idf = pd.DataFrame(filas)
pivot = df_idf.pivot(index="Duración (min)", columns="T (años)", values="Intensidad (mm/h)")

c1, c2 = st.columns([1, 2])
with c1:
    st.dataframe(pivot, use_container_width=True)
with c2:
    fig = go.Figure()
    for tr in trs_curva:
        sub = df_idf[df_idf["T (años)"] == tr]
        fig.add_trace(go.Scatter(x=sub["Duración (min)"], y=sub["Intensidad (mm/h)"], mode="lines+markers", name=f"T={tr} años"))
    fig.update_layout(xaxis_title="Duración (min)", yaxis_title="Intensidad (mm/h)", title="Curvas I-D-T")
    st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("3. Hietograma de diseño (Método del Bloque Alterno)")

manual_tr = st.checkbox("Ingresar el periodo de retorno T manualmente")

c1, c2, c3 = st.columns(3)
with c1:
    if manual_tr:
        tr_hieto = st.number_input("Periodo de retorno T (años)", min_value=1.0, value=71.0, step=1.0)
    else:
        tr_hieto = st.selectbox("Periodo de retorno T (años)", sorted(p24h_por_tr))
with c2:
    duracion_total_h = st.number_input("Duración total de la tormenta (h)", 1.0, 48.0, 24.0, step=1.0)
with c3:
    dt_h = st.number_input("Intervalo Δt (h)", 0.0833, 6.0, 1.0, step=0.25)

df_hieto = hy.bloque_alterno(intensidad_fn, tr_hieto, duracion_total_h, dt_h)

if "hietogramas" not in st.session_state:
    st.session_state["hietogramas"] = {}
st.session_state["hietogramas"][tr_hieto] = df_hieto

st.dataframe(df_hieto.round(2), use_container_width=True, height=420)

fig2 = go.Figure()
fig2.add_trace(go.Bar(x=df_hieto["duracion_h"], y=df_hieto["hietograma_mm"]))
fig2.update_layout(
    title=f"Hietograma de diseño - Tr = {tr_hieto} años",
    xaxis_title="Duración (h)", yaxis_title="Precipitación (mm)",
    height=450,
)
st.plotly_chart(fig2, use_container_width=True)
st.metric("Precipitación máxima del bloque (mm)", f"{df_hieto['hietograma_mm'].max():.2f}")

st.success(
    "Curvas IDF e hietograma calculados. Repite este paso para cada periodo de retorno de "
    "interés (los hietogramas quedan guardados para el cálculo de caudales)."
)

st.divider()
st.subheader("4. Reporte de hietogramas para varios periodos de retorno")
st.caption(
    "Genera un Excel con el hietograma de diseño de cada periodo de retorno que elijas, "
    "usando la misma duración total y Δt configurados arriba."
)

trs_texto_reporte = st.text_input(
    "Periodos de retorno T (años) a incluir en el reporte, separados por coma",
    ", ".join(map(str, sorted(p24h_por_tr))),
    key="trs_reporte_excel",
)
try:
    trs_reporte = sorted({float(t.strip()) for t in trs_texto_reporte.split(",") if t.strip()})
except ValueError:
    st.error("Ingresa solo números separados por coma.")
    st.stop()

def _escribir_hoja_hietograma(workbook, nombre_hoja, tr, df_t):
    ws = workbook.add_worksheet(nombre_hoja)

    fmt_titulo = workbook.add_format({"bold": True, "align": "center", "valign": "vcenter", "font_size": 12})
    fmt_header = workbook.add_format(
        {"bold": True, "align": "center", "valign": "vcenter", "text_wrap": True, "border": 1, "bg_color": "#D9E1F2"}
    )
    fmt_num = workbook.add_format({"num_format": "0.00", "border": 1})
    fmt_max_lbl = workbook.add_format({"bold": True, "align": "right"})
    fmt_max_val = workbook.add_format({"bold": True, "num_format": "0.00"})

    n = len(df_t)
    encabezados = [
        "DURACIÓN (hr)", "DURACIÓN (min)", "INTENSIDAD (mm/hr)",
        "PROFUNDIDAD ACUMULADA (mm)", "PROFUNDIDAD INCREMENTAL (mm)",
        "TIEMPO", "PRECIPITACIÓN (mm)",
    ]
    ws.merge_range(0, 0, 0, len(encabezados) - 1, f"HIETOGRAMA DE DISEÑO PARA TR = {tr:g} AÑOS", fmt_titulo)
    for col, h in enumerate(encabezados):
        ws.write(2, col, h, fmt_header)

    dur_h = df_t["duracion_h"].to_numpy()
    for i in range(n):
        row = 3 + i
        t_ini = dur_h[i - 1] if i > 0 else 0.0
        t_fin = dur_h[i]
        etiqueta_tiempo = f"{t_ini:g}-{t_fin:g}"
        ws.write_number(row, 0, df_t["duracion_h"].iloc[i], fmt_num)
        ws.write_number(row, 1, df_t["duracion_min"].iloc[i], fmt_num)
        ws.write_number(row, 2, df_t["intensidad_mm_h"].iloc[i], fmt_num)
        ws.write_number(row, 3, df_t["prof_acumulada_mm"].iloc[i], fmt_num)
        ws.write_number(row, 4, df_t["prof_incremental_mm"].iloc[i], fmt_num)
        ws.write(row, 5, etiqueta_tiempo, fmt_num)
        ws.write_number(row, 6, df_t["hietograma_mm"].iloc[i], fmt_num)

    fila_max = 3 + n + 1
    ws.merge_range(fila_max, 0, fila_max, 5, "Máxima precipitación =", fmt_max_lbl)
    ws.write_number(fila_max, 6, float(df_t["hietograma_mm"].max()), fmt_max_val)
    ws.set_column(0, 6, 16)

    chart = workbook.add_chart({"type": "column"})
    chart.add_series(
        {
            "name": f"Hietograma Tr={tr:g} años",
            "categories": [nombre_hoja, 3, 5, 3 + n - 1, 5],
            "values": [nombre_hoja, 3, 6, 3 + n - 1, 6],
        }
    )
    chart.set_title({"name": f"HIETOGRAMA DE DISEÑO TR = {tr:g} AÑOS"})
    chart.set_x_axis({"name": "Duración (Hr)"})
    chart.set_y_axis({"name": "Precipitación (mm)"})
    chart.set_legend({"none": True})
    chart.set_size({"width": 620, "height": 320})
    ws.insert_chart(fila_max + 3, 0, chart)


if st.button("📊 Generar reporte Excel", type="primary"):
    hietogramas_reporte = {}
    resumen_filas = []
    for t in trs_reporte:
        df_t = hy.bloque_alterno(intensidad_fn, t, duracion_total_h, dt_h)
        hietogramas_reporte[t] = df_t
        resumen_filas.append(
            {
                "T (años)": t,
                "Duración total (h)": duracion_total_h,
                "Δt (h)": dt_h,
                "Precipitación máxima del bloque (mm)": round(df_t["hietograma_mm"].max(), 2),
                "Precipitación total (mm)": round(df_t["hietograma_mm"].sum(), 2),
            }
        )

    if "hietogramas" not in st.session_state:
        st.session_state["hietogramas"] = {}
    st.session_state["hietogramas"].update(hietogramas_reporte)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        pd.DataFrame(resumen_filas).to_excel(writer, index=False, sheet_name="Resumen")
        workbook = writer.book
        for t, df_t in hietogramas_reporte.items():
            nombre_hoja = f"T={t:g} años"[:31]
            _escribir_hoja_hietograma(workbook, nombre_hoja, t, df_t)

    st.session_state["reporte_hietogramas_excel"] = buffer.getvalue()
    st.session_state["reporte_hietogramas_resumen"] = pd.DataFrame(resumen_filas)

if "reporte_hietogramas_excel" in st.session_state:
    st.dataframe(st.session_state["reporte_hietogramas_resumen"], use_container_width=True, hide_index=True)
    st.download_button(
        "⬇️ Descargar reporte de hietogramas (Excel)",
        st.session_state["reporte_hietogramas_excel"],
        file_name="hietogramas_diseno.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

st.sidebar.divider()
st.sidebar.caption("HIDROPro v1.0 · Creado por el Ing. Daniel Oliden")
