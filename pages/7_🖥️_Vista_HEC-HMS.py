import datetime as dt

import plotly.graph_objects as go
import streamlit as st

from hydro import scs

st.set_page_config(page_title="Vista HEC-HMS", page_icon="🖥️", layout="wide")
st.title("🖥️ Vista tipo HEC-HMS")

st.markdown(
    """
Esta vista presenta los mismos resultados de **📈 Caudal de Diseño** con el formato del
**Basin Model** y el **Global Summary Results** de HEC-HMS, para comparar visualmente
contra una corrida real del software.
"""
)

faltantes = []
if "cuencas" not in st.session_state:
    faltantes.append("🗺️ Cuencas (datos topográficos)")
if "tabla_scs" not in st.session_state:
    faltantes.append("📈 Caudal de Diseño (calcula los caudales primero)")
if faltantes:
    st.warning("Completa antes: " + ", ".join(faltantes))
    st.stop()

cuencas = st.session_state["cuencas"]
tabla_scs = st.session_state["tabla_scs"]
trs_usados = st.session_state.get("trs_calculo_usados", [])

st.subheader("Basin Model")

n = len(cuencas)
fig_bm = go.Figure()
x_sb, x_sink = 0.0, 1.0
for i, (_, r) in enumerate(cuencas.iterrows()):
    y = n - i
    nombre = str(r["Nombre"])
    obra = str(r.get("Obra de drenaje", "Salida"))
    fig_bm.add_shape(
        type="rect", x0=x_sb - 0.28, x1=x_sb + 0.28, y0=y - 0.22, y1=y + 0.22,
        line=dict(color="#4472A8", width=2), fillcolor="#bcd6f2", layer="above",
    )
    fig_bm.add_annotation(x=x_sb, y=y, text=f"<b>{nombre}</b><br>Subbasin", showarrow=False,
                           font=dict(size=11, color="#1a1a1a"))
    fig_bm.add_annotation(
        x=x_sink, y=y, ax=x_sb + 0.30, ay=y, axref="x", ayref="y",
        xref="x", yref="y", showarrow=True, arrowhead=3, arrowsize=1.2,
        arrowcolor="#8fa8c8", arrowwidth=2, text="",
    )
    fig_bm.add_trace(go.Scatter(
        x=[x_sink], y=[y], mode="markers+text", marker=dict(symbol="triangle-down", size=26,
        color="#f2c96b", line=dict(color="#8a6d1f", width=2)),
        text=[obra], textposition="bottom center", textfont=dict(size=10, color="#e6e6e6"),
        showlegend=False, hoverinfo="text", hovertext=f"{nombre} → {obra}",
    ))
fig_bm.update_xaxes(visible=False, range=[-0.6, 1.6])
fig_bm.update_yaxes(visible=False, range=[0.3, n + 0.7])
fig_bm.update_layout(
    height=max(220, 70 * n), plot_bgcolor="#1e2530", paper_bgcolor="#1e2530",
    margin=dict(l=10, r=10, t=10, b=10),
)
st.plotly_chart(fig_bm, use_container_width=True)
st.caption(
    "Cada cuenca/subcuenca se modela de forma independiente (drena directamente a su propia "
    "obra de drenaje), igual que en el Basin Model real del proyecto."
)

st.divider()
st.subheader("Global Summary Results")

MESES = {1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
         7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"}


def _fmt_fecha(t: dt.datetime) -> str:
    return f"{t.day:02d}{MESES[t.month]}.{t.year}, {t.hour:02d}:{t.minute:02d}"


inicio = dt.datetime(2025, 6, 4, 0, 0)
hietogramas = st.session_state.get("hietogramas", {})
dur_total_h = 24.0
if trs_usados and trs_usados[0] in hietogramas:
    dur_total_h = float(hietogramas[trs_usados[0]]["duracion_h"].max())
fin = inicio + dt.timedelta(hours=dur_total_h)

for idx_tr, tr in enumerate(trs_usados, start=1):
    col_area = "Área (km2)"
    col_q = f"Q SCS - TR={tr} años (m3/s)"
    col_vol = f"Volumen escorrentía - TR={tr} años (mm)"
    col_tp = f"Tiempo al pico - TR={tr} años (h)"

    filas_html = ""
    for _, r in tabla_scs.iterrows():
        t_pico = inicio + dt.timedelta(hours=float(r.get(col_tp, 0.0)))
        filas_html += (
            "<tr>"
            f"<td style='text-align:left;padding:4px 8px;'>{r['Nombre']}</td>"
            f"<td style='text-align:right;padding:4px 8px;'>{r[col_area]:.3f}</td>"
            f"<td style='text-align:right;padding:4px 8px;font-weight:bold;'>{r.get(col_q, 0):.1f}</td>"
            f"<td style='text-align:center;padding:4px 8px;'>{_fmt_fecha(t_pico)}</td>"
            f"<td style='text-align:right;padding:4px 8px;'>{r.get(col_vol, 0):.2f}</td>"
            "</tr>"
        )

    html = f"""
    <div style="border:1px solid #6b7280; border-radius:3px; margin-bottom:22px; font-family:'Segoe UI',sans-serif; overflow:hidden;">
      <div style="background:#2f6fb0; color:white; padding:5px 10px; font-size:13px; display:flex; justify-content:space-between;">
        <span>📊 Global Summary Results for Run &quot;Tr={tr:g} años&quot;</span>
        <span>— &nbsp; □ &nbsp; ×</span>
      </div>
      <div style="background:#f4f6f8; color:#1a1a1a; padding:8px 12px; font-size:12px; display:grid; grid-template-columns:1fr 1fr 1fr; gap:2px 18px;">
        <div><b>Project:</b> CAU_HIDRO_CUEN</div>
        <div><b>Start of Run:</b> {_fmt_fecha(inicio)}</div>
        <div><b>Basin Model:</b> Cuencas</div>
        <div><b>Simulation Run:</b> Tr={tr:g} años</div>
        <div><b>End of Run:</b> {_fmt_fecha(fin)}</div>
        <div><b>Meteorologic Model:</b> Met {idx_tr}</div>
        <div></div>
        <div><b>Compute Time:</b> DATA CHANGED, RECOMPUTE</div>
        <div><b>Control Specifications:</b> Control 1</div>
      </div>
      <table style="width:100%; border-collapse:collapse; font-size:12px; background:#0f1620; color:#e6e6e6;">
        <thead>
          <tr style="background:#243447; border-bottom:1px solid #6b7280;">
            <th style="text-align:left;padding:5px 8px;">Hydrologic Element</th>
            <th style="text-align:right;padding:5px 8px;">Drainage Area<br/>(KM2)</th>
            <th style="text-align:right;padding:5px 8px;">Peak Discharge<br/>(M3/S)</th>
            <th style="text-align:center;padding:5px 8px;">Time of Peak</th>
            <th style="text-align:right;padding:5px 8px;">Volume<br/>(MM)</th>
          </tr>
        </thead>
        <tbody>
          {filas_html}
        </tbody>
      </table>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

st.caption(
    "💡 Esta tabla usa exactamente los mismos resultados de **Q SCS** y **Volumen escorrentía** "
    "calculados en 📈 Caudal de Diseño — solo se presentan con el formato del Global Summary "
    "Results de HEC-HMS para facilitar la comparación visual contra una corrida real."
)

series_hidrograma = st.session_state.get("series_hidrograma", {})

if series_hidrograma:
    st.divider()
    st.subheader("Time Series Results")
    st.caption(
        "Hidrograma de creciente completo (Q vs. tiempo), calculado con el paso de cómputo interno "
        "configurado en 📈 Caudal de Diseño — no solo el caudal pico, sino la serie completa punto "
        "por punto, igual que la vista 'Time Series Results' de HEC-HMS."
    )

    claves = list(series_hidrograma.keys())
    c1, c2 = st.columns(2)
    with c1:
        nombre_sel = st.selectbox("Cuenca/subcuenca", sorted({k[0] for k in claves}), key="ts_nombre")
    with c2:
        tr_sel = st.selectbox("Periodo de retorno T (años)", sorted({k[1] for k in claves if k[0] == nombre_sel}), key="ts_tr")

    serie = series_hidrograma.get((nombre_sel, tr_sel))
    if serie:
        fig_ts = go.Figure()
        fig_ts.add_trace(go.Scatter(
            x=serie["t_h"], y=serie["q_m3s"], mode="lines", fill="tozeroy",
            line=dict(color="#3b82f6", width=2), fillcolor="rgba(59,130,246,0.15)",
            name=f"{nombre_sel} — TR={tr_sel:g} años",
        ))
        i_pico = int(serie["q_m3s"].argmax())
        fig_ts.add_trace(go.Scatter(
            x=[serie["t_h"][i_pico]], y=[serie["q_m3s"][i_pico]], mode="markers+text",
            marker=dict(color="#f2c96b", size=9, line=dict(color="#8a6d1f", width=1)),
            text=[f"Qmax={serie['q_m3s'][i_pico]:.2f} m³/s"], textposition="top center",
            showlegend=False,
        ))
        fig_ts.update_layout(
            title=f"Hidrograma de creciente — {nombre_sel}, TR={tr_sel:g} años (Δt cómputo = {serie['dt_h']*60:.1f} min)",
            xaxis_title="Tiempo (h)", yaxis_title="Caudal (m³/s)", height=420,
        )
        st.plotly_chart(fig_ts, use_container_width=True)
        with st.expander("Ver tabla de la serie de tiempo completa"):
            st.dataframe(
                {"t (h)": serie["t_h"].round(3), "Q (m3/s)": serie["q_m3s"].round(4)},
                use_container_width=True, height=300,
            )

    st.divider()
    st.subheader("Tabla de convolución paso a paso")
    st.caption(
        "Mecanismo interno del cálculo: cada pulso de lluvia efectiva (Pe) se multiplica por el "
        "hidrograma unitario completo, desplazado a su instante de inicio; la suma de todos los "
        "pulsos desplazados en cada fila da el caudal total en ese instante — exactamente como "
        "combina HEC-HMS el método de pérdidas ('Loss') con el de transformación ('Transform'). "
        "Se muestran solo los pulsos de mayor magnitud como columnas individuales (el resto se "
        "agrupa en 'Otros pulsos menores') para que la tabla sea legible; el total sí incluye todos."
    )
    if serie:
        tabla_conv = scs.tabla_convolucion(serie["pe_mm"], serie["hu"], serie["dt_h"], max_pulsos=24)
        st.dataframe(tabla_conv.round(4), use_container_width=True, height=380)
        st.metric("Q total máximo de la tabla (m³/s)", f"{tabla_conv['Q total (m3/s)'].max():.3f}")

_col_sig1, _col_sig2 = st.columns([3, 1])
with _col_sig2:
    if st.button("Diseño Hidráulico →", type="primary", use_container_width=True):
        st.switch_page("pages/8_📐_Diseño_Hidraulico.py")

st.sidebar.divider()
st.sidebar.caption("HIDROPro v1.0 · Creado por el Ing. Daniel Oliden")
