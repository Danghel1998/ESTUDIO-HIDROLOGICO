import pandas as pd
import streamlit as st

from hydro import returnperiod as rp

st.set_page_config(page_title="Período de Retorno", page_icon="⏱️", layout="wide")
st.title("⏱️ Período de retorno de diseño")

st.markdown(
    """
Según el Manual de Hidrología, Hidráulica y Drenaje del MTC, el período de retorno
de diseño se obtiene a partir del **riesgo admisible** y la **vida útil** de cada
tipo de obra:

$$T = \\dfrac{1}{1-(1-R)^{1/n}}$$

Puedes usar los valores recomendados por el manual o editarlos según el criterio de tu proyecto.
"""
)

if "obras_retorno_input" not in st.session_state:
    base_rows = []
    for obra, vals in rp.OBRAS_MTC.items():
        base_rows.append({"Obra de drenaje": obra, "Riesgo admisible (%)": vals["riesgo"] * 100, "Vida útil (años)": vals["vida_util"]})
    st.session_state["obras_retorno_input"] = pd.DataFrame(base_rows)

# No se retroalimenta `edited` como `data` en cada rerun: así se evita que
# Streamlit reaplique ediciones internas sobre datos que ya las contienen
# (perdiendo texto recién tipeado, sobre todo en filas agregadas).
edited = st.data_editor(
    st.session_state["obras_retorno_input"],
    use_container_width=True,
    hide_index=True,
    num_rows="dynamic",
    key="editor_periodos_retorno",
    column_config={
        "Riesgo admisible (%)": st.column_config.NumberColumn(format="%.0f %%", min_value=1, max_value=99),
        "Vida útil (años)": st.column_config.NumberColumn(format="%d", min_value=1),
    },
)

edited = edited.dropna()
edited["T (años)"] = edited.apply(
    lambda row: round(rp.periodo_retorno(row["Riesgo admisible (%)"] / 100, row["Vida útil (años)"])), axis=1
)

st.dataframe(edited, use_container_width=True, hide_index=True)

st.session_state["periodos_retorno_obras"] = dict(zip(edited["Obra de drenaje"], edited["T (años)"]))

st.divider()
st.subheader("Calculadora rápida")
c1, c2, c3 = st.columns(3)
with c1:
    r_in = st.number_input("Riesgo admisible R (%)", 1, 99, 30) / 100
with c2:
    n_in = st.number_input("Vida útil n (años)", 1, 200, 25)
with c3:
    st.metric("Período de retorno T (años)", f"{rp.periodo_retorno(r_in, n_in):.1f}")

st.success(
    "Estos periodos de retorno se usarán en los pasos siguientes (curvas IDF, hietograma "
    "y caudal de diseño) para cada tipo de obra."
)

_col_sig1, _col_sig2 = st.columns([3, 1])
with _col_sig2:
    if st.button("Curvas IDF e Hietograma →", type="primary", use_container_width=True):
        st.switch_page("pages/4_🌧️_IDF_Hietograma.py")

st.sidebar.divider()
st.sidebar.caption("HIDROPro v1.0 · Creado por el Ing. Daniel Oliden")
