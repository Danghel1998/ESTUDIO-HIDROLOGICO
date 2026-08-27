import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from hydro import frequency, outliers

st.set_page_config(page_title="Análisis de Frecuencias", page_icon="📊", layout="wide")
st.title("📊 Análisis estadístico de datos hidrológicos")

if "station_data" not in st.session_state or st.session_state["station_data"] is None:
    st.warning("Primero carga la serie de la estación en **📥 Datos de estación**.")
    st.stop()

df = st.session_state["station_data"].copy()

st.subheader("1. Análisis estadístico de datos — Prueba de datos dudosos")
st.caption("Método del U.S. Water Resources Council, sobre log10(Pmax24h). Mismas fórmulas que Hidroesta 2.")

work = df.copy()
if "P24h_original" not in work.columns:
    work["P24h_original"] = work["P24h"]

datos_mensuales = st.session_state.get("datos_mensuales")

activos = work.sort_values("Año").reset_index(drop=True)
x_activos = activos["P24h"].to_numpy(dtype=float)
res = outliers.outlier_test(x_activos)

tabla_datos = activos[["Año", "P24h"]].copy()
tabla_datos.insert(0, "N°", range(1, len(tabla_datos) + 1))
tabla_datos["Log(P24hr)"] = np.log10(tabla_datos["P24h"])
tabla_datos = tabla_datos.rename(columns={"P24h": "P24hr"})

stats_p = outliers.estadisticos_descriptivos(x_activos)
stats_log = outliers.estadisticos_descriptivos(np.log10(x_activos))

filas_stats = [
    ("Número de datos (N)", "n", "{:.2f}"),
    ("Sumatoria", "suma", "{:.2f}"),
    ("Valor Máximo", "maximo", "{:.2f}"),
    ("Valor Mínimo", "minimo", "{:.2f}"),
    ("Media", "media", "{:.4f}"),
    ("Varianza", "varianza", "{:.4f}"),
    ("Desviación Estándar", "desv_std", "{:.4f}"),
    ("Coeficiente Variación", "coef_variacion", "{:.4f}"),
    ("Coeficiente de Sesgo", "coef_sesgo", "{:.4f}"),
    ("Coeficiente de Curtosis", "coef_curtosis", "{:.4f}"),
]
tabla_stats = pd.DataFrame(
    {
        "Parámetro estadístico": [f for f, _, _ in filas_stats],
        "P24hr": [fmt.format(stats_p[k]) for _, k, fmt in filas_stats],
        "Log(P24hr)": [fmt.format(stats_log[k]) for _, k, fmt in filas_stats],
    }
)

c1, c2 = st.columns([1, 1])
with c1:
    st.markdown("**Precipitación máxima 24 horas**")
    st.dataframe(tabla_datos.round(4), use_container_width=True, hide_index=True, height=400)
with c2:
    st.markdown("**Parámetros estadísticos**")
    st.dataframe(tabla_stats, use_container_width=True, hide_index=True, height=390)

cn1, cn2 = st.columns(2)
cn1.metric("n", f"{res['n']:.2f}")
cn2.metric("Kn (significancia 10%)", f"{res['kn']:.2f}")
st.caption("Kn: valor recomendado, varía según el valor de n.")

st.markdown("##### Umbral de datos dudosos altos (xH: unidad logarítmica)")
bh1, bh2 = st.columns([2, 1])
with bh1:
    st.latex(r"x_H = \bar{x} + k_n \cdot s")
    st.write(f"xH = **{res['mean_log'] + res['kn'] * res['std_log']:.4f}**")
    st.write(f"Precipitación máxima aceptada: PH = 10^xH = **{res['umbral_alto']:.2f} mm**")
with bh2:
    st.metric("xH", f"{res['mean_log'] + res['kn'] * res['std_log']:.2f}")
    st.metric("PH (mm)", f"{res['umbral_alto']:.2f}")
if res["hay_outliers_altos"]:
    st.error("⚠️ EXISTEN DATOS DUDOSOS ALTOS EN LA MUESTRA")
else:
    st.success("✅ NO EXISTEN DATOS DUDOSOS ALTOS EN LA MUESTRA")

st.markdown("##### Umbral de datos dudosos bajos (xL: unidad logarítmica)")
bl1, bl2 = st.columns([2, 1])
with bl1:
    st.latex(r"x_L = \bar{x} - k_n \cdot s")
    st.write(f"xL = **{res['mean_log'] - res['kn'] * res['std_log']:.4f}**")
    st.write(f"Precipitación mínima aceptada: PL = 10^xL = **{res['umbral_bajo']:.2f} mm**")
with bl2:
    st.metric("xL", f"{res['mean_log'] - res['kn'] * res['std_log']:.2f}")
    st.metric("PL (mm)", f"{res['umbral_bajo']:.2f}")
if res["hay_outliers_bajos"]:
    st.error("⚠️ EXISTEN DATOS DUDOSOS BAJOS EN LA MUESTRA")
else:
    st.success("✅ NO EXISTEN DATOS DUDOSOS BAJOS EN LA MUESTRA")

if res["hay_outliers_altos"] or res["hay_outliers_bajos"]:
    st.divider()
    st.warning(
        "Existen datos fuera de los umbrales aceptables. Según el criterio recomendado, **no se "
        "elimina el año completo de la muestra**: se reemplaza el valor dudoso por la segunda "
        "precipitación máxima registrada ese mismo año (si tienes el detalle mensual), y se "
        "vuelve a evaluar manteniendo el mismo número de datos (n)."
    )
    outl_vals = list(res["outliers_altos"]) + list(res["outliers_bajos"])
    anios_flag = work.loc[work["P24h"].isin(outl_vals), "Año"].tolist()

    for anio in anios_flag:
        fila_idx = work.index[work["Año"] == anio][0]
        valor_actual = float(work.loc[fila_idx, "P24h"])

        st.markdown(f"**Año {anio} — valor dudoso: {valor_actual:.2f} mm**")
        sugerido = valor_actual
        if datos_mensuales is not None and anio in datos_mensuales.index:
            fila_meses = datos_mensuales.loc[anio].dropna().sort_values(ascending=False)
            st.dataframe(
                fila_meses.rename("Precipitación (mm)").to_frame().T,
                use_container_width=True, hide_index=True,
            )
            if len(fila_meses) >= 2:
                sugerido = float(fila_meses.iloc[1])
                st.caption(
                    f"Segunda precipitación más alta de {anio}: **{sugerido:.2f} mm** "
                    "(valor sugerido para reemplazar el dudoso)."
                )
        else:
            st.caption(
                "No se cargó el detalle mensual de este año (importaste la serie ya como "
                "máximo anual). Ingresa manualmente la segunda precipitación más alta de ese "
                "año, según tu registro original de SENAMHI."
            )

        cc1, cc2 = st.columns([1, 2])
        with cc1:
            nuevo_valor = st.number_input(
                f"Valor corregido para {anio} (mm)", min_value=0.0, value=round(sugerido, 2),
                step=0.1, key=f"corr_{anio}",
            )
        with cc2:
            st.write("")
            st.write("")
            if st.button(f"Aplicar corrección a {anio}", key=f"btn_corr_{anio}"):
                work.loc[fila_idx, "P24h"] = nuevo_valor
                st.session_state["station_data"] = work
                st.rerun()

corregidos = work[work["P24h"] != work["P24h_original"]]
if len(corregidos) > 0:
    st.divider()
    st.info(
        "Años con valor corregido: "
        + ", ".join(
            f"{int(r.Año)} ({r.P24h_original:.2f} → {r.P24h:.2f} mm)" for r in corregidos.itertuples()
        )
    )
    if st.button("↩️ Deshacer todas las correcciones"):
        work["P24h"] = work["P24h_original"]
        st.session_state["station_data"] = work
        st.rerun()

serie_final = work.sort_values("Año").reset_index(drop=True)
st.session_state["station_data"] = work
st.session_state["serie_frecuencias"] = serie_final

st.divider()
st.markdown("#### ANÁLISIS ESTADÍSTICO DE DATOS DE PRECIPITACIONES MÁXIMAS EN 24H CORREGIDO (mm)")
tabla_corregida = serie_final[["Año", "P24h"]].rename(columns={"P24h": "Ppmax (mm)"}).copy()
tabla_corregida.insert(0, "N°", range(1, len(tabla_corregida) + 1))
tabla_corregida["Ppmax (mm)"] = tabla_corregida["Ppmax (mm)"].round(2)
st.dataframe(tabla_corregida, use_container_width=True, hide_index=True, height=min(35 * len(tabla_corregida) + 38, 500))

st.divider()
st.subheader("2. Ajuste de distribuciones de probabilidad")

x = serie_final["P24h"].to_numpy(dtype=float)
if len(x) < 5:
    st.error("Se requieren al menos 5 datos para el análisis de frecuencias.")
    st.stop()

resultados = frequency.fit_all(x)
st.session_state["dist_results"] = {r.name: r for r in resultados}
mejor = resultados[0]

st.markdown("#### Prueba de bondad de ajuste Smirnov-Kolmogorov")

orden_original = [
    "Normal", "Log Normal 2 parámetros", "Log Normal 3 parámetros", "Gamma 2 parámetros",
    "Gamma 3 parámetros", "Log Pearson tipo III", "Gumbel", "Log Gumbel",
]
por_nombre = {r.name: r for r in resultados}
en_orden = [por_nombre[n] for n in orden_original if n in por_nombre]

d_crit = resultados[0].ks_crit
fila_delta = {"Δ TABULAR": f"{d_crit:.4f}"}
for r in en_orden:
    fila_delta[r.name.upper()] = f"{r.ks_d:.4f}" if not np.isnan(r.ks_d) else "—"
tabla_bondad = pd.DataFrame([fila_delta])
st.dataframe(tabla_bondad, use_container_width=True, hide_index=True)
st.caption(f"**MIN Δ = {mejor.ks_d:.4f}** → distribución **{mejor.name.upper()}**")

st.markdown("###### Comparación empírica vs. teórica (función de distribución acumulada)")

filas_grid, cols_grid = 2, 4
fig_grid = make_subplots(
    rows=filas_grid, cols=cols_grid,
    subplot_titles=[r.name for r in en_orden],
)
for i, r in enumerate(en_orden):
    row = i // cols_grid + 1
    col = i % cols_grid + 1
    fig_grid.add_trace(
        go.Scatter(
            x=r.x_sorted, y=r.cdf_empirica, mode="lines+markers", name="Empírica",
            marker=dict(size=4, color="#2E86DE"), line=dict(color="#2E86DE"),
            showlegend=(i == 0), legendgroup="emp",
        ),
        row=row, col=col,
    )
    fig_grid.add_trace(
        go.Scatter(
            x=r.x_sorted, y=r.cdf_teorica, mode="lines", name="Teórica",
            line=dict(color="#10AC84", dash="dot"),
            showlegend=(i == 0), legendgroup="teo",
        ),
        row=row, col=col,
    )
fig_grid.update_layout(height=480, margin=dict(t=40, b=10))
fig_grid.update_yaxes(range=[0, 1])
st.plotly_chart(fig_grid, use_container_width=True)

st.success(f"El modelo de distribución que mejor se ajusta a la serie de datos es: **{mejor.name.upper()}**")

nombres = [r.name for r in resultados]
seleccion = st.selectbox(
    "Distribución a usar para el diseño", nombres, index=nombres.index(mejor.name)
)
dist_elegida = st.session_state["dist_results"][seleccion]
st.session_state["distribucion_seleccionada"] = seleccion

with st.expander("Ver parámetros de la distribución elegida"):
    st.json({k: (round(v, 5) if isinstance(v, (int, float)) else v) for k, v in dist_elegida.params.items()})

st.divider()
st.subheader("3. Cálculo de precipitaciones")

trs_default = [2, 5, 10, 20, 30, 50, 80, 100, 140, 200, 500]
trs_text = st.text_input("Periodos de retorno T (años), separados por coma", ", ".join(map(str, trs_default)))
try:
    trs = sorted({int(t.strip()) for t in trs_text.split(",") if t.strip()})
except ValueError:
    st.error("Ingresa solo números enteros separados por coma.")
    st.stop()

p24h_sin_corregir = {tr: dist_elegida.value_for_return_period(tr) for tr in trs}

st.markdown("###### Precipitación máxima para diferentes periodos de retorno")
col_dist = f"DISTRIBUCION {seleccion.upper()}"
tabla_calc = pd.DataFrame(
    {
        "T (años)": [str(tr) for tr in trs],
        "P": [round(1 / tr, 3) for tr in trs],
        col_dist: [round(p24h_sin_corregir[tr], 2) for tr in trs],
    }
)
fila_delta_calc = pd.DataFrame(
    [{"T (años)": "Δ", "P": round(d_crit, 3), col_dist: round(mejor.ks_d, 3)}]
)
st.dataframe(pd.concat([tabla_calc, fila_delta_calc], ignore_index=True), use_container_width=True, hide_index=True)

st.divider()
st.markdown("###### Relación entre precipitación máxima verdadera y precipitación en intervalos fijos")
st.caption("Fuente: Hidrología para ingenieros (Linsley, Kohler y Paulhus)")

tabla_relacion = pd.DataFrame(
    {
        "Número de intervalo de observación": ["1", "2", "3-4", "5-8", "3-24"],
        "Relación": [1.13, 1.04, 1.03, 1.02, 1.01],
    }
)
c1, c2 = st.columns([1, 1])
with c1:
    st.dataframe(tabla_relacion, use_container_width=True, hide_index=True)
with c2:
    manual_factor = st.checkbox("Ingresar f manualmente")
    if manual_factor:
        factor = st.number_input(
            "Factor de corrección f",
            min_value=0.5, max_value=2.0, value=1.13, step=0.01, format="%.4f",
            help="La tabla de la izquierda se multiplica directamente por este valor de f.",
        )
    else:
        opciones_factor = {"1 (registro fijo diario, típico SENAMHI)": 1.13, "2": 1.04, "3-4": 1.03, "5-8": 1.02, "3-24": 1.01, "Sin corrección": 1.0}
        factor_sel = st.selectbox(
            "Número de intervalo de observación de tu registro",
            list(opciones_factor.keys()),
            help=(
                "Pmax24h obtenida de lecturas fijas (p.ej. una lectura diaria a la misma hora) "
                "subestima la verdadera lluvia máxima en 24h continuas. Se corrige multiplicando "
                "por este factor (Weiss, 1964). Por defecto se asume registro diario fijo (factor "
                "1.13), que es el caso típico de las estaciones SENAMHI y el que aplican los "
                "estudios de hidrología vial del MTC; cambia a 'Sin corrección' si tu registro ya "
                "es de lluvia máxima continua en 24h, o activa 'Ingresar f manualmente' para un "
                "valor propio."
            ),
        )
        factor = opciones_factor[factor_sel]
    st.metric("Factor de corrección", f"{factor:.4f}")

p24h_por_tr = {tr: v * factor for tr, v in p24h_sin_corregir.items()}
st.session_state["p24h_por_tr"] = p24h_por_tr

st.markdown("###### Precipitación máxima corregida por intervalo fijo de observación")
tabla_corr = pd.DataFrame(
    {
        "T (años)": trs,
        "P": [round(1 / tr, 3) for tr in trs],
        f"{col_dist} (sin corregir)": [round(p24h_sin_corregir[tr], 2) for tr in trs],
        "Factor": factor,
        f"{col_dist} corregida": [round(p24h_por_tr[tr], 2) for tr in trs],
    }
)
st.dataframe(tabla_corr, use_container_width=True, hide_index=True)

fig = go.Figure()
fig.add_trace(go.Scatter(x=trs, y=[p24h_por_tr[t] for t in trs], mode="lines+markers", name="Corregida"))
fig.add_trace(
    go.Scatter(x=trs, y=[p24h_sin_corregir[t] for t in trs], mode="lines+markers", name="Sin corregir", line=dict(dash="dot"))
)
fig.update_layout(
    xaxis_title="Período de retorno T (años)", yaxis_title="Pmax24h (mm)", xaxis_type="log", height=450
)
st.plotly_chart(fig, use_container_width=True)

st.success("Listo. Continúa con **⏱️ Período de retorno** o **🌧️ Curvas IDF e Hietograma**.")

_col_sig1, _col_sig2, _col_sig3 = st.columns([2, 1, 1])
with _col_sig2:
    if st.button("⏱️ Período de retorno →", use_container_width=True):
        st.switch_page("pages/3_⏱️_Periodo_Retorno.py")
with _col_sig3:
    if st.button("🌧️ Curvas IDF e Hietograma →", type="primary", use_container_width=True):
        st.switch_page("pages/4_🌧️_IDF_Hietograma.py")

st.sidebar.divider()
st.sidebar.caption("HIDROPro v1.0 · Creado por el Ing. Daniel Oliden")
