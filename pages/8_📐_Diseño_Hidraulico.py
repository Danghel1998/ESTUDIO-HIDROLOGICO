import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from hydro import canales as ca

st.set_page_config(page_title="Diseño Hidráulico", page_icon="📐", layout="wide")
st.title("📐 Diseño hidráulico de canales")

st.markdown(
    """
Dimensiona la sección hidráulica (cuneta, canal, badén o alcantarilla) que debe llevar el
**caudal de diseño** ya calculado — mismo alcance que el software **H Canales** (M. Villón),
usando los criterios de borde libre y rugosidad del **Manual de Hidrología, Hidráulica y
Drenaje del MTC**.
"""
)

st.subheader("1. Caudal de diseño")

resumen = st.session_state.get("resumen_caudales")
origen_manual = st.checkbox("Ingresar el caudal manualmente")
obra_sel = None
nombre_sel = None
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

MODULOS = [
    "Tirante-Normal", "Tirante-Crítico", "Resalto-Hidráulico", "Remanso",
    "Caudales", "Otros", "Medición", "Estructuras",
]
modulo = st.radio(
    "Módulo de cálculo", MODULOS, horizontal=True, key="modulo_hcanales",
    label_visibility="collapsed",
)

st.divider()


def _input_geometria(prefix: str, seccion_default: str = "Trapezoidal", incluir_circular: bool = True):
    """Selector de forma + dimensiones de la sección (sin n ni S) — reusado
    por los módulos que no dependen de la pendiente/rugosidad del cauce."""
    opciones = list(ca.SECCIONES.keys()) if incluir_circular else [s for s in ca.SECCIONES if s != "Circular"]
    seccion = st.selectbox(
        "Forma de la sección", opciones, index=opciones.index(seccion_default), key=f"{prefix}_seccion",
    )
    kw = {}
    if seccion == "Circular":
        d = st.number_input("Diámetro (D)", min_value=0.10, value=1.00, step=0.05, format="%.2f", key=f"{prefix}_d")
        st.caption("m")
        kw["d"] = d
    else:
        b = st.number_input(
            "Ancho de solera (b)", min_value=0.0, value=0.60 if seccion != "Rectangular" else 1.00,
            step=0.05, format="%.2f", key=f"{prefix}_b",
        )
        st.caption("m")
        kw["b"] = b
    if seccion in ("Trapezoidal", "Triangular"):
        z = st.number_input(
            "Talud (Z)", min_value=0.0, value=1.0, step=0.1, format="%.2f",
            help="Horizontal por cada 1 vertical", key=f"{prefix}_z",
        )
        kw["z"] = z
    return seccion, kw


def _fig_seccion_con_agua(seccion: str, kw: dict, tirantes: list, altura_ref: float = None):
    """Dibuja el contorno de la sección y, superpuestos, los tirantes dados
    como (etiqueta, y, color, opacidad). `altura_ref` fija la escala del
    contorno (por defecto, el mayor tirante a dibujar)."""
    y_max_dibujo = altura_ref or max(y for _, y, _, _ in tirantes) * 1.15
    fig = go.Figure()
    if seccion == "Circular":
        d = kw["d"]
        th = np.linspace(0, 2 * np.pi, 200)
        fig.add_trace(go.Scatter(x=d / 2 * np.cos(th), y=d / 2 * np.sin(th) + d / 2, mode="lines",
                                  line=dict(color="#8a6d1f", width=3), name="Tubería"))
        ang_full = np.linspace(-np.pi, np.pi, 400)
        y_circ = d / 2 * np.sin(ang_full) + d / 2
        for etiqueta, y, color, opacidad in tirantes:
            mascara = y_circ <= y
            if not mascara.any():
                continue
            xw = (d / 2 * np.cos(ang_full))[mascara]
            yw = y_circ[mascara]
            fig.add_trace(go.Scatter(x=np.concatenate([xw, [xw[0]]]), y=np.concatenate([yw, [yw[0]]]), fill="toself",
                                      fillcolor=color, opacity=opacidad, line=dict(color=color), name=etiqueta))
        fig.update_yaxes(scaleanchor="x", range=[-0.1 * d, d * 1.1])
    else:
        b_ = kw.get("b", 0.0)
        z_ = kw.get("z", 0.0)
        half_top = b_ / 2 + z_ * y_max_dibujo
        xs = [-half_top, -b_ / 2, b_ / 2, half_top]
        ys = [y_max_dibujo, 0, 0, y_max_dibujo]
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color="#8a6d1f", width=3), name="Sección"))
        for etiqueta, y, color, opacidad in tirantes:
            half_top_w = b_ / 2 + z_ * y
            xw = [-half_top_w, -b_ / 2, b_ / 2, half_top_w]
            yw = [y, 0, 0, y]
            fig.add_trace(go.Scatter(x=xw, y=yw, fill="toself", fillcolor=color, opacity=opacidad,
                                      line=dict(color=color), name=etiqueta))
            fig.add_hline(y=y, line_dash="dot", line_color=color, annotation_text=f"{etiqueta}={y:.2f}m")
        fig.update_yaxes(scaleanchor="x")
    fig.update_layout(xaxis_title="(m)", yaxis_title="(m)", height=380, showlegend=True)
    return fig


def _fig_esquema_ilustrativo(seccion: str, kw: dict):
    """Esquema ilustrativo de la forma de sección (proporciones fijas, no a
    escala real) con las etiquetas T/y/Z/b — mismo estilo que H Canales."""
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
        fig_esquema.add_annotation(x=0, y=y_ill * 1.18, text="T", showarrow=False, font=dict(size=16, color="#0b3d91"))
        fig_esquema.add_annotation(x=half_top + 0.18, y=y_ill / 2, text="y", showarrow=False, font=dict(size=16, color="#0b3d91"))
        if seccion != "Rectangular":
            fig_esquema.add_annotation(x=-half_bot / 2 - half_top / 4, y=y_ill / 2, text="Z", showarrow=False, font=dict(size=14, color="#0b3d91"))
            fig_esquema.add_annotation(x=-(half_bot + half_top) / 4, y=y_ill / 2 + 0.14, text="1", showarrow=False, font=dict(size=12, color="#0b3d91"))
        if half_bot > 0:
            fig_esquema.add_annotation(x=0, y=-0.08, text="b", showarrow=False, font=dict(size=16, color="#0b3d91"))
    fig_esquema.update_xaxes(visible=False)
    fig_esquema.update_yaxes(visible=False, scaleanchor="x")
    fig_esquema.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="#eaf2fb", paper_bgcolor="#eaf2fb")
    return fig_esquema


def _modulo_tirante_normal(q_diseno, obra_sel, nombre_sel, resumen, origen_manual):
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
            st.plotly_chart(_fig_esquema_ilustrativo(seccion, kw), use_container_width=True)
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

        y_dibujo = yn + bl
        fig = _fig_seccion_con_agua(seccion, kw, [("yn", yn, "#3b82f6", 0.35)], altura_ref=y_dibujo)
        fig.update_layout(title=f"Sección {seccion.lower()} — {tipo_obra}")
        st.plotly_chart(fig, use_container_width=True)

    except ValueError as e:
        st.error(f"No se pudo resolver el tirante normal: {e}")


def _modulo_tirante_critico(q_diseno):
    st.subheader("2. Datos")
    col_datos, col_dibujo = st.columns([1, 1])
    with col_datos:
        with st.container(border=True):
            seccion, kw = _input_geometria("yc")
            st.metric("Caudal (Q)", f"{q_diseno:.3f} m³/s")
            st.caption(
                "El tirante crítico depende solo de Q y la geometría (no de la rugosidad n "
                "ni de la pendiente S): es el tirante para el cual la energía específica es mínima."
            )
    with col_dibujo:
        with st.container(border=True):
            st.plotly_chart(_fig_esquema_ilustrativo(seccion, kw), use_container_width=True)
            st.caption(f"Esquema ilustrativo — sección {seccion.lower()}")

    st.divider()
    st.subheader("3. Resultados")
    try:
        yc = ca.tirante_critico(q_diseno, seccion, **kw)
        vc = ca.velocidad(q_diseno, yc, seccion, **kw)
        fr = ca.numero_froude(q_diseno, yc, seccion, **kw)
        prop = ca.propiedades_seccion(yc, seccion, **kw)
        ec = ca.energia_especifica(q_diseno, yc, seccion, **kw)

        with st.container(border=True):
            rc1, rc2 = st.columns(2)
            with rc1:
                st.metric("Tirante crítico (yc)", f"{yc:.4f} m")
                st.metric("Área hidráulica crítica (Ac)", f"{prop['area']:.4f} m²")
                st.metric("Espejo de agua crítico (Tc)", f"{prop['espejo']:.4f} m")
                st.metric("Número de Froude", f"{fr:.4f} (= 1 por definición)")
            with rc2:
                st.metric("Perímetro (Pc)", f"{prop['perimetro']:.4f} m")
                st.metric("Radio hidráulico (Rc)", f"{prop['radio_hidraulico']:.4f} m")
                st.metric("Velocidad crítica (vc)", f"{vc:.4f} m/s")
                st.metric("Energía específica mínima (Ec)", f"{ec:.4f} m")

        fig = _fig_seccion_con_agua(seccion, kw, [("yc", yc, "#ef4444", 0.35)])
        fig.update_layout(title=f"Sección {seccion.lower()} — tirante crítico")
        st.plotly_chart(fig, use_container_width=True)

    except ValueError as e:
        st.error(f"No se pudo resolver el tirante crítico: {e}")


def _modulo_resalto(q_diseno):
    st.subheader("2. Datos")
    col_datos, col_dibujo = st.columns([1, 1])
    with col_datos:
        with st.container(border=True):
            seccion, kw = _input_geometria("rh", "Rectangular")
            st.metric("Caudal (Q)", f"{q_diseno:.3f} m³/s")
            y1 = st.number_input(
                "Tirante antes del resalto y1 (m) — flujo supercrítico", min_value=0.001,
                value=0.30, step=0.01, format="%.3f",
                help="Tirante de llegada al pie de una estructura (rápida, vertedero, salida de "
                "alcantarilla con pendiente fuerte, etc.), donde el flujo es supercrítico.",
            )
    with col_dibujo:
        with st.container(border=True):
            st.plotly_chart(_fig_esquema_ilustrativo(seccion, kw), use_container_width=True)
            st.caption(f"Esquema ilustrativo — sección {seccion.lower()}")

    st.divider()
    st.subheader("3. Resultados")
    try:
        yc = ca.tirante_critico(q_diseno, seccion, **kw)
        if y1 >= yc:
            st.warning(
                f"⚠️ y1 ({y1:.3f} m) no es menor que el tirante crítico yc ({yc:.3f} m): el flujo "
                "no es supercrítico y no se forma un resalto hidráulico real. Ingresa un y1 menor a yc."
            )
        y2 = ca.tirante_conjugado(q_diseno, y1, seccion, **kw)
        fr1 = ca.numero_froude(q_diseno, y1, seccion, **kw)
        fr2 = ca.numero_froude(q_diseno, y2, seccion, **kw)
        v1 = ca.velocidad(q_diseno, y1, seccion, **kw)
        v2 = ca.velocidad(q_diseno, y2, seccion, **kw)
        e1 = ca.energia_especifica(q_diseno, y1, seccion, **kw)
        e2 = ca.energia_especifica(q_diseno, y2, seccion, **kw)
        delta_e = e1 - e2

        with st.container(border=True):
            rc1, rc2 = st.columns(2)
            with rc1:
                st.metric("Tirante antes (y1)", f"{y1:.4f} m")
                st.metric("Número de Froude (F1)", f"{fr1:.4f}")
                st.metric("Velocidad (v1)", f"{v1:.4f} m/s")
                st.metric("Energía específica (E1)", f"{e1:.4f} m")
            with rc2:
                st.metric("Tirante conjugado (y2)", f"{y2:.4f} m")
                st.metric("Número de Froude (F2)", f"{fr2:.4f}")
                st.metric("Velocidad (v2)", f"{v2:.4f} m/s")
                st.metric("Energía específica (E2)", f"{e2:.4f} m")
            st.metric("Pérdida de energía en el resalto (ΔE = E1 − E2)", f"{delta_e:.4f} m")
            st.caption(f"Tirante crítico de referencia (yc) = {yc:.4f} m")

        fig = _fig_seccion_con_agua(
            seccion, kw,
            [("y2", y2, "#3b82f6", 0.30), ("y1", y1, "#ef4444", 0.55)],
        )
        fig.update_layout(title=f"Sección {seccion.lower()} — y1 (antes) y y2 (después) del resalto")
        st.plotly_chart(fig, use_container_width=True)

    except ValueError as e:
        st.error(f"No se pudo resolver el resalto hidráulico: {e}")


def _modulo_remanso(q_diseno):
    SUBMETODOS = ["Integración Gráfica", "Bakhmeteff", "Bresse", "Directo por Tramos", "Tramos Fijos"]
    submetodo = st.selectbox("Método de cálculo de la curva de remanso", SUBMETODOS, key="remanso_metodo")

    if submetodo in ("Bakhmeteff", "Bresse"):
        st.info(
            f"🚧 El método **{submetodo}** (funciones de flujo variado tabuladas F(u,N)) todavía no "
            "está implementado — usa **Integración Gráfica** o **Directo por Tramos**: resuelven la "
            "misma ecuación diferencial del flujo gradualmente variado sin necesitar tablas, y dan "
            "resultados equivalentes."
        )
        return

    es_tramos_fijos = submetodo == "Tramos Fijos"

    st.subheader("2. Datos")
    col_datos, col_dibujo = st.columns([1, 1])
    with col_datos:
        with st.container(border=True):
            seccion, kw = _input_geometria("rm", "Trapezoidal", incluir_circular=False)
            st.metric("Caudal (Q)", f"{q_diseno:.3f} m³/s")

            nombres_n = list(ca.MANNING_N.keys())
            material = st.selectbox("Material / revestimiento", nombres_n, key="rm_material")
            manual_n = st.checkbox("Ingresar rugosidad (n) manualmente", key="rm_manual_n")
            n_manning = (
                st.number_input("Rugosidad (n)", min_value=0.008, max_value=0.15, value=ca.MANNING_N[material], step=0.001, format="%.3f", key="rm_n")
                if manual_n else ca.MANNING_N[material]
            )
            if not manual_n:
                st.caption(f"n = {n_manning:.3f} ({material})")

            s_fondo = st.number_input("Pendiente (S)", min_value=0.00001, value=0.00100, step=0.00010, format="%.5f", key="rm_s")
            st.caption("m/m")

            if es_tramos_fijos:
                yi = st.number_input("Tirante inicial (yi)", min_value=0.001, value=1.00, step=0.05, format="%.3f", key="rm_yi")
                nt = st.number_input("Número de tramos (nt)", min_value=1, value=10, step=1, key="rm_nt_fijo")
                dx = st.number_input("Distancia de cada tramo (Δx)", min_value=0.1, value=50.0, step=1.0, format="%.2f", key="rm_dx")
            else:
                y1 = st.number_input("Tirante inicial (y1)", min_value=0.001, value=1.00, step=0.05, format="%.3f", key="rm_y1")
                y2 = st.number_input("Tirante final (y2)", min_value=0.001, value=1.50, step=0.05, format="%.3f", key="rm_y2")
                nt = st.number_input("Número de tramos (nt)", min_value=1, value=10, step=1, key="rm_nt")

    with col_dibujo:
        with st.container(border=True):
            st.plotly_chart(_fig_esquema_ilustrativo(seccion, kw), use_container_width=True)
            st.caption(f"Esquema ilustrativo — sección {seccion.lower()}")
            try:
                yn_ref = ca.tirante_normal(q_diseno, n_manning, s_fondo, seccion, **kw)
                yc_ref = ca.tirante_critico(q_diseno, seccion, **kw)
                rcol1, rcol2 = st.columns(2)
                rcol1.metric("Tirante normal (yn)", f"{yn_ref:.4f} m")
                rcol2.metric("Tirante crítico (yc)", f"{yc_ref:.4f} m")
            except ValueError:
                pass

    st.divider()
    st.subheader("3. Resultados")

    try:
        if es_tramos_fijos:
            filas = ca.perfil_remanso_tramos_fijos(q_diseno, n_manning, s_fondo, seccion, yi, int(nt), dx, **kw)
            df = pd.DataFrame(filas).rename(columns={"x": "x (m)", "y": "y (m)"})
            if len(filas) - 1 < nt:
                st.warning(
                    f"⚠️ El perfil se detuvo en x = {filas[-1]['x (m)' if 'x (m)' in df.columns else 'x']:.2f} m "
                    f"(tramo {len(filas) - 1} de {int(nt)}): el tirante se acerca asintóticamente al normal o "
                    "crítico y un paso Δx fijo ya no puede resolverse ahí. Usa **Directo por Tramos** o "
                    "**Integración Gráfica** para continuar el perfil (marchan por incrementos de tirante, no de distancia)."
                )
            st.dataframe(df.round(4), use_container_width=True, hide_index=True)
            col_x, col_y = "x (m)", "y (m)"

        elif submetodo == "Directo por Tramos":
            filas = ca.perfil_remanso_directo_por_tramos(q_diseno, n_manning, s_fondo, seccion, y1, y2, int(nt), **kw)
            df = pd.DataFrame(filas).rename(columns={
                "y": "y (m)", "A": "A (m²)", "P": "P (m)", "R": "R (m)", "R23": "R^(2/3)",
                "v": "v (m/s)", "v2_2g": "v²/2g (m)", "E": "E (m)", "deltaE": "ΔE (m)",
                "Se": "Se", "SeP": "SeP", "So_SeP": "So−SeP", "deltax": "Δx (m)", "x": "x (m)",
            })
            st.dataframe(df.round(4), use_container_width=True, hide_index=True)
            col_x, col_y = "x (m)", "y (m)"

        else:  # Integración Gráfica
            filas = ca.perfil_remanso_integracion_grafica(q_diseno, n_manning, s_fondo, seccion, y1, y2, int(nt), **kw)
            df = pd.DataFrame(filas).rename(columns={
                "y": "y (m)", "A": "A (m²)", "P": "P (m)", "R": "R (m)", "T": "T (m)", "v": "v (m/s)",
                "Se": "Se", "uno_menos_Q2T_gA3": "1−Q²T/gA³", "So_Se": "So−Se", "f_y": "f(y)",
                "deltax": "Δx (m)", "x": "x (m)",
            })
            st.dataframe(df.round(4), use_container_width=True, hide_index=True)
            col_x, col_y = "x (m)", "y (m)"

        fig_perfil = go.Figure()
        fig_perfil.add_trace(go.Scatter(x=df[col_x], y=df[col_y], mode="lines+markers", name="y(x)"))
        try:
            fig_perfil.add_hline(y=yn_ref, line_dash="dot", line_color="#3b82f6", annotation_text=f"yn={yn_ref:.2f}m")
            fig_perfil.add_hline(y=yc_ref, line_dash="dot", line_color="#ef4444", annotation_text=f"yc={yc_ref:.2f}m")
        except NameError:
            pass
        fig_perfil.update_layout(
            title=f"Perfil de flujo (curva de remanso) — {submetodo}",
            xaxis_title="x (m)", yaxis_title="y (m)", height=420,
        )
        st.plotly_chart(fig_perfil, use_container_width=True)

    except ValueError as e:
        st.error(f"No se pudo calcular el perfil de remanso: {e}")


def _modulo_caudales():
    st.caption(
        "Calcula el caudal (Q) y las propiedades hidráulicas para un **tirante dado** — el cálculo "
        "inverso de Tirante Normal. No usa el caudal ingresado en el paso 1 (aquí Q es un resultado, no un dato)."
    )
    st.subheader("2. Datos")
    col_datos, col_dibujo = st.columns([1, 1])
    with col_datos:
        with st.container(border=True):
            seccion, kw = _input_geometria("cq", "Trapezoidal", incluir_circular=True)
            if seccion == "Circular":
                y_tope = kw["d"] - 0.001
                y = st.number_input(
                    "Tirante (y)", min_value=0.001, max_value=y_tope, value=min(0.50, y_tope),
                    step=0.01, format="%.3f", key="cq_y", help="Debe ser menor que el diámetro D.",
                )
            else:
                y = st.number_input("Tirante (y)", min_value=0.001, value=0.50, step=0.01, format="%.3f", key="cq_y")
            st.caption("m")

            nombres_n = list(ca.MANNING_N.keys())
            material = st.selectbox("Material / revestimiento", nombres_n, key="cq_material")
            manual_n = st.checkbox("Ingresar rugosidad (n) manualmente", key="cq_manual_n")
            n_manning = (
                st.number_input("Rugosidad (n)", min_value=0.008, max_value=0.15, value=ca.MANNING_N[material], step=0.001, format="%.3f", key="cq_n")
                if manual_n else ca.MANNING_N[material]
            )
            if not manual_n:
                st.caption(f"n = {n_manning:.3f} ({material})")

            s_fondo = st.number_input("Pendiente (S)", min_value=0.00001, value=0.02000, step=0.00100, format="%.5f", key="cq_s")
            st.caption("m/m")

    with col_dibujo:
        with st.container(border=True):
            st.plotly_chart(_fig_esquema_ilustrativo(seccion, kw), use_container_width=True)
            st.caption(f"Esquema ilustrativo — sección {seccion.lower()}")

    st.divider()
    st.subheader("3. Resultados")

    try:
        q = ca.caudal_manning(y, n_manning, s_fondo, seccion, **kw)
        v = ca.velocidad(q, y, seccion, **kw)
        fr = ca.numero_froude(q, y, seccion, **kw)
        prop = ca.propiedades_seccion(y, seccion, **kw)
        e_esp = ca.energia_especifica(q, y, seccion, **kw)
        regimen = "Supercrítico" if fr > 1.0 else ("Crítico" if abs(fr - 1.0) < 1e-3 else "Subcrítico")

        with st.container(border=True):
            rc1, rc2 = st.columns(2)
            with rc1:
                st.metric("Caudal (Q)", f"{q:.4f} m³/s")
                st.metric("Área hidráulica (A)", f"{prop['area']:.4f} m²")
                st.metric("Radio hidráulico (R)", f"{prop['radio_hidraulico']:.4f} m")
                st.metric("Número de Froude (F)", f"{fr:.4f}")
                st.metric("Tipo de flujo", regimen)
            with rc2:
                st.metric("Velocidad (v)", f"{v:.4f} m/s")
                st.metric("Perímetro (P)", f"{prop['perimetro']:.4f} m")
                st.metric("Espejo de agua (T)", f"{prop['espejo']:.4f} m")
                st.metric("Energía específica (E)", f"{e_esp:.4f} m")

        fig = _fig_seccion_con_agua(seccion, kw, [("y", y, "#3b82f6", 0.35)])
        fig.update_layout(title=f"Sección {seccion.lower()}")
        st.plotly_chart(fig, use_container_width=True)

    except ValueError as e:
        st.error(f"No se pudo calcular el caudal: {e}")


if modulo == "Tirante-Normal":
    _modulo_tirante_normal(q_diseno, obra_sel, nombre_sel, resumen, origen_manual)
elif modulo == "Tirante-Crítico":
    _modulo_tirante_critico(q_diseno)
elif modulo == "Resalto-Hidráulico":
    _modulo_resalto(q_diseno)
elif modulo == "Remanso":
    _modulo_remanso(q_diseno)
elif modulo == "Caudales":
    _modulo_caudales()
else:
    st.info(
        f"🚧 El módulo **{modulo}** (como en H Canales) todavía no está implementado en esta "
        "interfaz — no forma parte del alcance típico del diseño hidráulico vial del Manual MTC "
        "(alcantarillas, badenes y cunetas), que solo requiere Tirante Normal, Tirante Crítico y, "
        "en obras con flujo rápido, Resalto Hidráulico."
    )

st.sidebar.divider()
st.sidebar.caption("HIDROPro v1.0 · Creado por el Ing. Daniel Oliden")
