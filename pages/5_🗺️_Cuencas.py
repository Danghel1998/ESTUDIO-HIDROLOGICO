import numpy as np
import pandas as pd
import streamlit as st

from hydro import basin

st.set_page_config(page_title="Cuencas", page_icon="🗺️", layout="wide")
st.title("🗺️ Cuencas y subcuencas — datos topográficos")

st.markdown(
    """
Ingresa aquí los **datos topográficos** de cada cuenca/subcuenca (obtenidos de tu
levantamiento topográfico, DEM o cartografía) por cada cauce que cruza la vía/obra.
Con esta información se calculan los parámetros geomorfológicos y el tiempo de
concentración necesarios para estimar el caudal de diseño.
"""
)

cols = [
    "Nombre", "Progresiva", "Área (km2)", "Perímetro (km)",
    "Long. cauce principal (km)", "Cota máxima (m)", "Cota mínima (m)",
    "N° de Curva CN", "Obra de drenaje",
]
if "cuencas_input" not in st.session_state:
    st.session_state["cuencas_input"] = pd.DataFrame(
        {
            "Nombre": ["C-01"], "Progresiva": ["00+000"], "Área (km2)": [1.0],
            "Perímetro (km)": [4.0], "Long. cauce principal (km)": [1.5],
            "Cota máxima (m)": [500.0], "Cota mínima (m)": [400.0],
            "N° de Curva CN": [80.0], "Obra de drenaje": ["Alcantarilla"],
        }
    )

# Ejemplo real: cuenca C-01 y subcuencas SC-01..SC-05 del proyecto AM-512
# (Aramango - Bagua - Amazonas), tal como figuran en el estudio de hidrología
# de referencia. Las cotas no vienen dadas en el estudio (solo longitud y
# pendiente del cauce); se fijan cota mínima=100 m y cota máxima tal que
# (cota_max - cota_min)/(L*1000) reproduzca exactamente la pendiente reportada.
_EJEMPLO_REAL = {
    "Nombre": ["C-01", "SC-01", "SC-02", "SC-03", "SC-04", "SC-05"],
    "Progresiva": ["03+500.00", "03+758.00", "03+980.00", "08+115.00", "08+305.00", "08+556.00"],
    "Área (km2)": [2.494, 0.103, 0.106, 0.096, 0.109, 0.094],
    "Perímetro (km)": [8.5371, 2.0794, 1.6157, 1.3869, 1.3340, 1.2047],
    "Long. cauce principal (km)": [3.1187, 0.0625, 0.2846, 0.0799, 0.1288, 0.3069],
    "N° de Curva CN": [88.0, 88.0, 88.0, 88.0, 88.0, 88.0],
    "Obra de drenaje": ["Baden", "Alcantarilla", "Alcantarilla", "Alcantarilla", "Alcantarilla", "Alcantarilla"],
}
_pendientes_ref = [0.1116, 0.2320, 0.2020, 0.1439, 0.2562, 0.1874]
_cota_min_ref = 100.0
_EJEMPLO_REAL["Cota mínima (m)"] = [_cota_min_ref] * 6
_EJEMPLO_REAL["Cota máxima (m)"] = [
    round(_cota_min_ref + s * l * 1000, 2)
    for s, l in zip(_pendientes_ref, _EJEMPLO_REAL["Long. cauce principal (km)"])
]

if st.button("📂 Cargar ejemplo real (proyecto AM-512: C-01 + 5 subcuencas)"):
    st.session_state["cuencas_input"] = pd.DataFrame(_EJEMPLO_REAL)[cols]
    st.rerun()

st.session_state.setdefault("editor_cuencas_version", 0)
ncb1, ncb2 = st.columns([2, 1])
with ncb1:
    cn_bulk = st.number_input(
        "N° de Curva CN a aplicar a todas las cuencas/subcuencas", min_value=30.0, max_value=100.0,
        value=88.0, step=1.0, key="cn_bulk_valor",
    )
with ncb2:
    st.write("")
    st.write("")
    if st.button("⬇️ Aplicar CN a todas las filas"):
        st.session_state["cuencas_input"]["N° de Curva CN"] = cn_bulk
        st.session_state["editor_cuencas_version"] += 1
        st.rerun()

# Importante: se pasa siempre el mismo objeto en session_state como `data` y
# NUNCA se reasigna desde el valor devuelto por el editor. Si se retroalimenta
# el resultado como entrada en cada rerun, Streamlit puede volver a aplicar
# las ediciones internas (sobre todo filas agregadas con num_rows="dynamic")
# sobre datos que ya las contienen, y el texto recién tipeado se pierde.
edited = st.data_editor(
    st.session_state["cuencas_input"], num_rows="dynamic", use_container_width=True,
    key=f"editor_cuencas_{st.session_state['editor_cuencas_version']}",
    column_config={
        "Área (km2)": st.column_config.NumberColumn(format="%.4f"),
        "Perímetro (km)": st.column_config.NumberColumn(format="%.4f"),
        "Long. cauce principal (km)": st.column_config.NumberColumn(format="%.4f"),
        "Cota máxima (m)": st.column_config.NumberColumn(format="%.2f"),
        "Cota mínima (m)": st.column_config.NumberColumn(format="%.2f"),
        "N° de Curva CN": st.column_config.NumberColumn(format="%.1f", min_value=30, max_value=100),
    },
)

_opciones_tc = list(basin.TC_METODOS.keys()) + ["Promedio de las 4 fórmulas"]
metodo_tc = st.selectbox(
    "Fórmula de tiempo de concentración a usar para el caudal de diseño",
    _opciones_tc,
    index=_opciones_tc.index("US Corps of Engineers"),
    help=(
        "Las 4 fórmulas usan la misma pendiente S (m/m) pero dan resultados muy distintos entre "
        "sí (para C-01 del proyecto AM-512: Kirpich=0.37h, Hathaway=1.25h, Bransby-Williams=1.07h, "
        "US Corps=1.08h). US Corps of Engineers es la que reproduce exactamente el Tc de los "
        "estudios de hidrología vial del MTC usados como referencia en esta app; cambia la fórmula "
        "aquí si tu proyecto usa otro criterio."
    ),
)

df = edited.dropna(subset=["Área (km2)", "Perímetro (km)", "Long. cauce principal (km)", "Cota máxima (m)", "Cota mínima (m)"]).copy()

if len(df) > 0:
    df["Desnivel (m)"] = df["Cota máxima (m)"] - df["Cota mínima (m)"]
    df["Pendiente S (m/m)"] = df["Desnivel (m)"] / (df["Long. cauce principal (km)"] * 1000)
    df["Ancho medio W (km)"] = df.apply(lambda r: basin.ancho_medio(r["Área (km2)"], r["Long. cauce principal (km)"]), axis=1)
    df["Coef. compacidad Kc"] = df.apply(lambda r: basin.coef_compacidad(r["Perímetro (km)"], r["Área (km2)"]), axis=1)
    df["Factor de forma Ff"] = df.apply(lambda r: basin.factor_forma(r["Área (km2)"], r["Long. cauce principal (km)"]), axis=1)
    df["Clasificación"] = df["Área (km2)"].apply(basin.clasificacion_cuenca)

    tc_cols = {}
    for nombre, fn in basin.TC_METODOS.items():
        if nombre == "Bransby-Williams":
            tc_cols[nombre] = df.apply(lambda r: fn(r["Área (km2)"], r["Long. cauce principal (km)"], r["Pendiente S (m/m)"]), axis=1)
        else:
            tc_cols[nombre] = df.apply(lambda r: fn(r["Long. cauce principal (km)"], r["Pendiente S (m/m)"]), axis=1)
    for nombre, serie in tc_cols.items():
        df[f"Tc {nombre} (h)"] = serie

    if metodo_tc == "Promedio de las 4 fórmulas":
        df["Tc adoptado (h)"] = df[[f"Tc {n} (h)" for n in basin.TC_METODOS]].mean(axis=1)
    else:
        df["Tc adoptado (h)"] = df[f"Tc {metodo_tc} (h)"]

    st.session_state["cuencas"] = df

    st.divider()
    st.subheader("Parámetros geomorfológicos calculados")
    st.dataframe(
        df[
            [
                "Nombre", "Progresiva", "Área (km2)", "Clasificación", "Pendiente S (m/m)",
                "Ancho medio W (km)", "Coef. compacidad Kc", "Factor de forma Ff",
            ]
        ].round(4),
        use_container_width=True, hide_index=True,
    )

    st.subheader("Tiempo de concentración por método (horas)")
    with st.container(border=True):
        fc1, fc2, fc3, fc4 = st.columns(4)
        with fc1:
            st.markdown("**Kirpich**")
            st.latex(r"T_c = 0.06628\,L^{0.77}\,S^{-0.385}")
        with fc2:
            st.markdown("**Hathaway**")
            st.latex(r"T_c = \dfrac{0.606\,(L\,n)^{0.467}}{S^{0.234}}")
        with fc3:
            st.markdown("**Bransby-Williams**")
            st.latex(r"T_c = \dfrac{0.2433\,L}{A^{0.1}\,S^{0.2}}")
        with fc4:
            st.markdown("**US Corps of Engineers**")
            st.latex(r"T_c = \dfrac{0.3\,L^{0.76}}{S^{0.19}}")
        st.caption(
            "Tc en horas · L: longitud del cauce principal (km) · S: pendiente del cauce (m/m) · "
            "A: área de la cuenca (km²) · n: coeficiente de rugosidad (0.5 por defecto)"
        )
        st.dataframe(
            df[["Nombre", "Long. cauce principal (km)", "Pendiente S (m/m)", "Área (km2)"]].round(4),
            use_container_width=True, hide_index=True,
        )
    st.dataframe(
        df[["Nombre"] + [f"Tc {n} (h)" for n in basin.TC_METODOS] + ["Tc adoptado (h)"]].round(3),
        use_container_width=True, hide_index=True,
    )

    st.success(
        "Cuencas registradas. Continúa con **📈 Caudal de Diseño** para obtener el caudal "
        "máximo por el Método SCS y el Método Racional."
    )
else:
    st.info("Completa al menos una fila con área, perímetro, longitud y cotas del cauce.")

st.sidebar.divider()
st.sidebar.caption("HIDROPro v1.0 · Creado por el Ing. Daniel Oliden")
