import numpy as np
import plotly.graph_objects as go
import streamlit as st

from hydro import canales as ca

st.set_page_config(page_title="Diseño Hidráulico", page_icon="📐", layout="wide")
st.title("📐 Diseño hidráulico de canales")

st.markdown(
    """
Dimensiona la sección hidráulica (cuneta, canal, badén o alcantarilla) que debe llevar el
**caudal de diseño** ya calculado, por flujo uniforme (ecuación de Manning) — mismo alcance
que el software **H Canales** (M. Villón), usando los criterios de borde libre y rugosidad
del **Manual de Hidrología, Hidráulica y Drenaje del MTC**.
"""
)

st.subheader("1. Caudal de diseño")

resumen = st.session_state.get("resumen_caudales")
origen_manual = st.checkbox("Ingresar el caudal manualmente")
obra_sel = None
if origen_manual or resumen is None:
    if resumen is None:
        st.info("No hay caudales calculados en 📈 Caudal de Diseño todavía — ingresa Q manualmente.")
    q_diseno = st.number_input("Caudal de diseño Q (m³/s)", min_value=0.001, value=1.000, step=0.1, format="%.3f")
else:
    trs_usados = st.session_state.get("trs_calculo_usados", [])
    nombres = list(resumen["Nombre"])
    cc1, cc2 = st.columns(2)
    with cc1:
        nombre_sel = st.selectbox("Cuenca/subcuenca", nombres)
    with cc2:
        tr_sel = st.selectbox("Periodo de retorno T (años)", trs_usados)
    fila = resumen[resumen["Nombre"] == nombre_sel].iloc[0]
    q_diseno = float(fila[f"Q máx (Q) - TR={tr_sel} años (m3/s)"])
    obra_sel = str(fila.get("Obra de drenaje", ""))

st.divider()
st.subheader("2. Datos")

tipo_obra_opciones = ["Alcantarilla", "Badén", "Canal / cuneta"]
idx_default = 0
if obra_sel:
    for i, op in enumerate(tipo_obra_opciones):
        if op.lower().split()[0] in obra_sel.lower():
            idx_default = i

col_datos, col_dibujo = st.columns([1, 1])

with col_datos:
    with st.container(border=True):
        tipo_obra = st.radio("Tipo de obra de drenaje", tipo_obra_opciones, index=idx_default, horizontal=True)
        seccion_default = {"Alcantarilla": "Circular", "Badén": "Trapezoidal", "Canal / cuneta": "Trapezoidal"}[tipo_obra]
        seccion = st.selectbox(
            "Forma de la sección", list(ca.SECCIONES.keys()),
            index=list(ca.SECCIONES.keys()).index(seccion_default),
        )

        st.metric("Caudal (Q)", f"{q_diseno:.3f} m³/s")

        kw = {}
        if seccion == "Circular":
            d = st.number_input("Diámetro (D)", min_value=0.10, value=1.00, step=0.05, format="%.2f")
            st.caption("m")
            kw["d"] = d
        else:
            b = st.number_input("Ancho de solera (b)", min_value=0.0, value=0.60 if seccion != "Rectangular" else 1.00, step=0.05, format="%.2f")
            st.caption("m")
            kw["b"] = b

        if seccion in ("Trapezoidal", "Triangular"):
            z = st.number_input("Talud (Z)", min_value=0.0, value=1.0, step=0.1, format="%.2f", help="Horizontal por cada 1 vertical")
            kw["z"] = z

        nombres_n = list(ca.MANNING_N.keys())
        material = st.selectbox("Material / revestimiento", nombres_n)
        manual_n = st.checkbox("Ingresar rugosidad (n) manualmente")
        n_manning = (
            st.number_input("Rugosidad (n)", min_value=0.008, max_value=0.15, value=ca.MANNING_N[material], step=0.001, format="%.3f")
            if manual_n else ca.MANNING_N[material]
        )
        if not manual_n:
            st.caption(f"n = {n_manning:.3f} ({material}) — Tabla Nº 09, Manual MTC")

        pendiente_default = 0.02
        if resumen is not None and not origen_manual:
            cuencas_df = st.session_state.get("cuencas")
            if cuencas_df is not None and nombre_sel in list(cuencas_df["Nombre"]):
                pendiente_default = float(cuencas_df[cuencas_df["Nombre"] == nombre_sel]["Pendiente S (m/m)"].iloc[0])
        s_fondo = st.number_input(
            "Pendiente (S)", min_value=0.0001, value=round(pendiente_default, 4),
            step=0.001, format="%.4f",
            help="Por defecto se toma la pendiente del cauce de la cuenca seleccionada; ajústala si la obra tiene una pendiente longitudinal propia.",
        )
        st.caption("m/m")

with col_dibujo:
    with st.container(border=True):
        fig_esquema = go.Figure()
        if seccion == "Circular":
            th = np.linspace(0, 2 * np.pi, 100)
            fig_esquema.add_trace(go.Scatter(x=0.5 * np.cos(th), y=0.5 * np.sin(th) + 0.5, mode="lines",
                                              line=dict(color="#1a1a1a", width=3), fill="toself",
                                              fillcolor="#bcd6f2", showlegend=False))
            fig_esquema.add_annotation(x=0.6, y=0.5, text="D", showarrow=True, ax=40, ay=0, font=dict(size=16))
        else:
            z_ill = kw.get("z", 1.0) if seccion in ("Trapezoidal", "Triangular") else 0.0
            b_ill, y_ill = 0.6, 0.6
            half_top = b_ill / 2 + z_ill * y_ill
            half_bot = b_ill / 2 if seccion != "Triangular" else 0.0
            xs = [-half_top, -half_bot, half_bot, half_top]
            ys = [y_ill, 0, 0, y_ill]
            fig_esquema.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color="#1a1a1a", width=3),
                                              fill="toself", fillcolor="#bcd6f2", showlegend=False))
            fig_esquema.add_annotation(x=0, y=y_ill * 1.18, text=f"T", showarrow=False, font=dict(size=16, color="#0b3d91"))
            fig_esquema.add_annotation(x=half_top + 0.18, y=y_ill / 2, text="y", showarrow=False, font=dict(size=16, color="#0b3d91"))
            if seccion != "Rectangular":
                fig_esquema.add_annotation(x=-half_bot / 2 - half_top / 4, y=y_ill / 2, text="Z", showarrow=False, font=dict(size=14, color="#0b3d91"))
                fig_esquema.add_annotation(x=-(half_bot + half_top) / 4, y=y_ill / 2 + 0.14, text="1", showarrow=False, font=dict(size=12, color="#0b3d91"))
            if half_bot > 0:
                fig_esquema.add_annotation(x=0, y=-0.08, text="b", showarrow=False, font=dict(size=16, color="#0b3d91"))
        fig_esquema.update_xaxes(visible=False)
        fig_esquema.update_yaxes(visible=False, scaleanchor="x")
        fig_esquema.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="#eaf2fb", paper_bgcolor="#eaf2fb")
        st.plotly_chart(fig_esquema, use_container_width=True)
        st.caption(f"Esquema ilustrativo — sección {seccion.lower()}")

st.divider()
st.subheader("3. Resultados")

try:
    yn = ca.tirante_normal(q_diseno, n_manning, s_fondo, seccion, **kw)
    yc = ca.tirante_critico(q_diseno, seccion, **kw)
    v = ca.velocidad(q_diseno, yn, seccion, **kw)
    fr = ca.numero_froude(q_diseno, yn, seccion, **kw)
    prop = ca.propiedades_seccion(yn, seccion, **kw)
    e_esp = ca.energia_especifica(q_diseno, yn, seccion, **kw)
    regimen = "Supercrítico" if fr > 1.0 else ("Crítico" if abs(fr - 1.0) < 1e-3 else "Subcrítico")

    with st.container(border=True):
        rc1, rc2 = st.columns(2)
        with rc1:
            st.metric("Tirante normal (y)", f"{yn:.4f} m")
            st.metric("Área hidráulica (A)", f"{prop['area']:.4f} m²")
            st.metric("Espejo de agua (T)", f"{prop['espejo']:.4f} m")
            st.metric("Número de Froude (F)", f"{fr:.4f}")
            st.metric("Tipo de flujo", regimen)
        with rc2:
            st.metric("Perímetro (P)", f"{prop['perimetro']:.4f} m")
            st.metric("Radio hidráulico (R)", f"{prop['radio_hidraulico']:.4f} m")
            st.metric("Velocidad (v)", f"{v:.4f} m/s")
            st.metric("Energía específica (E)", f"{e_esp:.4f} m")
            st.metric("Tirante crítico (yc)", f"{yc:.4f} m")

    st.divider()
    st.subheader("4. Borde libre y verificación (criterios Manual MTC)")

    if tipo_obra == "Alcantarilla":
        altura_ref = kw.get("d", kw.get("b", yn))
        bl = ca.borde_libre_alcantarilla(altura_ref)
        bl_nota = f"25% de la altura/diámetro de la estructura ({altura_ref:.3f} m) — Manual MTC 4.1.1.3.6(b)"
    elif tipo_obra == "Badén":
        bl = st.slider(
            "Borde libre del badén (m) — Manual MTC recomienda 0.30 a 0.50 m", ca.BORDE_LIBRE_BADEN_MIN_M,
            ca.BORDE_LIBRE_BADEN_MAX_M, ca.BORDE_LIBRE_BADEN_DEFAULT_M, 0.01,
        )
        bl_nota = "Manual MTC 4.1.1.4.1(e): borde libre del badén, valor entre 0.30 y 0.50 m"
    else:
        bl = 0.25 * yn
        bl_nota = "Criterio general (25% del tirante normal), ajústalo según el proyecto"

    r5, r6, r7 = st.columns(3)
    r5.metric("Borde libre (m)", f"{bl:.3f}")
    r6.metric("Tirante total y + BL (m)", f"{yn + bl:.3f}")
    if seccion == "Circular":
        r7.metric("% de la sección llena", f"{100 * yn / kw['d']:.1f} %")
    st.caption(f"Borde libre: {bl_nota}")

    if v < ca.VELOCIDAD_MIN_MS:
        st.warning(f"⚠️ La velocidad ({v:.2f} m/s) es menor a la mínima recomendada ({ca.VELOCIDAD_MIN_MS} m/s) — riesgo de sedimentación.")
    st.caption(
        "Velocidad máxima admisible según material del cauce/revestimiento (referencial): "
        + ", ".join(f"{k}: {v_:.2f} m/s" for k, v_ in ca.VELOCIDAD_MAX_MS.items())
    )

    # --- Gráfico de la sección transversal a escala, con el tirante calculado ---
    y_dibujo = yn + bl
    fig = go.Figure()
    if seccion == "Circular":
        d = kw["d"]
        th = np.linspace(0, 2 * np.pi, 200)
        fig.add_trace(go.Scatter(x=d / 2 * np.cos(th), y=d / 2 * np.sin(th) + d / 2, mode="lines",
                                  line=dict(color="#8a6d1f", width=3), name="Tubería"))
        # Arco inferior de la tubería cubierto por el agua hasta el tirante yn
        # (y=0 en el fondo del tubo, y=d en la corona; centro del círculo en y=d/2).
        # ang_full ya está ordenado de -pi a pi, y la máscara conserva ese orden,
        # así que el arco resultante queda contiguo sin necesidad de reordenar.
        ang_full = np.linspace(-np.pi, np.pi, 400)
        y_circ = d / 2 * np.sin(ang_full) + d / 2
        mascara = y_circ <= yn
        xw = (d / 2 * np.cos(ang_full))[mascara]
        yw = y_circ[mascara]
        fig.add_trace(go.Scatter(x=np.concatenate([xw, [xw[0]]]), y=np.concatenate([yw, [yw[0]]]), fill="toself",
                                  fillcolor="rgba(59,130,246,0.35)", line=dict(color="#3b82f6"), name="Agua (yn)"))
        fig.update_yaxes(scaleanchor="x", range=[-0.1 * d, d * 1.1])
    else:
        b_ = kw.get("b", 0.0)
        z_ = kw.get("z", 0.0)
        half_top = b_ / 2 + z_ * y_dibujo
        half_bot = b_ / 2
        xs = [-half_top, -half_bot, half_bot, half_top]
        ys = [y_dibujo, 0, 0, y_dibujo]
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color="#8a6d1f", width=3), name="Sección"))
        half_top_w = b_ / 2 + z_ * yn
        xw = [-half_top_w, -half_bot, half_bot, half_top_w]
        yw = [yn, 0, 0, yn]
        fig.add_trace(go.Scatter(x=xw, y=yw, fill="toself", fillcolor="rgba(59,130,246,0.35)",
                                  line=dict(color="#3b82f6"), name="Agua (yn)"))
        fig.add_hline(y=yn, line_dash="dot", line_color="#3b82f6", annotation_text=f"yn={yn:.2f}m")
        fig.add_hline(y=y_dibujo, line_dash="dot", line_color="#f2c96b", annotation_text=f"yn+BL={y_dibujo:.2f}m")
        fig.update_yaxes(scaleanchor="x")

    fig.update_layout(title=f"Sección {seccion.lower()} — {tipo_obra}", xaxis_title="(m)", yaxis_title="(m)",
                       height=420, showlegend=True)
    st.plotly_chart(fig, use_container_width=True)

except ValueError as e:
    st.error(f"No se pudo resolver el tirante normal: {e}")
