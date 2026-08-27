import io

import pandas as pd
import plotly.express as px
import streamlit as st

from hydro import pdf_import, senamhi_estaciones

st.set_page_config(page_title="Datos de Estación", page_icon="📥", layout="wide")
st.title("📥 Datos de la estación SENAMHI")

st.markdown(
    """
Ingresa la serie de **precipitación máxima en 24 horas (Pmax24h)** de la estación
seleccionada por el método del polígono de Thiessen (la más cercana/representativa
de tu cuenca). El Manual MTC exige un mínimo recomendable de 25 años de registro.
"""
)

with st.expander(
    "🗺️ Mapa de estaciones SENAMHI (para ubicar la estación más cercana a tu cuenca)",
    expanded=False, key="map_expander",
):
    st.caption(
        "Ubicación de las 974 estaciones hidrometeorológicas publicadas en el "
        "[mapa oficial de SENAMHI](https://www.senamhi.gob.pe/mapas/mapa-estaciones-2/) "
        "(copia local — SENAMHI no ofrece una API pública para esta información). "
        "Úsalo para identificar, por cercanía a tu cuenca, la estación a usar en el "
        "método del polígono de Thiessen; luego descarga su serie histórica desde el "
        "portal de SENAMHI y súbela abajo."
    )

    df_est = senamhi_estaciones.cargar_estaciones()

    fc1, fc2, fc3 = st.columns([1.3, 1.7, 1.5])
    with fc1:
        tipos_sel = st.multiselect(
            "Tipo de estación", ["Meteorológica", "Hidrológica"],
            default=["Meteorológica", "Hidrológica"], key="map_tipo",
        )
    with fc2:
        estados_sel = st.multiselect(
            "Condición de recepción de datos",
            list(senamhi_estaciones.ESTADOS.values()),
            default=list(senamhi_estaciones.ESTADOS.values()), key="map_estado",
        )
    with fc3:
        busqueda = st.text_input(
            "Buscar por nombre o código", "", key="map_busqueda",
            placeholder="p.ej. BAGUA, 000253",
        )

    df_map = df_est[df_est["tipo"].isin(tipos_sel) & df_est["estado_desc"].isin(estados_sel)]
    if busqueda.strip():
        b = busqueda.strip().upper()
        df_map = df_map[
            df_map["nombre"].str.upper().str.contains(b)
            | df_map["codigo"].str.contains(b)
            | df_map["codigo_antiguo"].str.upper().str.contains(b)
        ]

    if len(df_map) == 0:
        st.info("Ninguna estación coincide con el filtro/búsqueda.")
    else:
        fig_map = px.scatter_map(
            df_map, lat="lat", lon="lon", color="tipo",
            color_discrete_map={"Meteorológica": "#2e7d32", "Hidrológica": "#1565c0"},
            hover_name="nombre",
            hover_data={"codigo": True, "categoria_desc": True, "estado_desc": True, "lat": False, "lon": False},
            custom_data=["nombre", "codigo"],
            zoom=4.4 if len(df_map) > 1 else 11,
            center={"lat": -9.19, "lon": -75.02} if len(df_map) > 1 else
                   {"lat": float(df_map["lat"].iloc[0]), "lon": float(df_map["lon"].iloc[0])},
            map_style="open-street-map",
            height=520,
        )
        fig_map.update_traces(marker={"size": 9})
        fig_map.update_layout(
            margin={"r": 0, "t": 0, "l": 0, "b": 0},
            legend={"orientation": "h", "yanchor": "bottom", "y": 1.01},
        )
        evento = st.plotly_chart(
            fig_map, use_container_width=True, on_select="rerun",
            selection_mode="points", key="mapa_senamhi",
        )
        st.caption(f"{len(df_map)} estación(es) mostradas. Haz clic en un punto del mapa para seleccionarlo.")

        puntos = evento.get("selection", {}).get("points", []) if evento else []
        if puntos:
            nom_sel, cod_sel = puntos[0]["customdata"][0], puntos[0]["customdata"][1]
            fila_sel = df_map[(df_map["nombre"] == nom_sel) & (df_map["codigo"] == cod_sel)].iloc[0]
            st.success(
                f"Seleccionada: **{fila_sel['nombre']}** — código `{fila_sel['codigo']}` "
                f"({fila_sel['categoria_desc']}, {fila_sel['estado_desc']})"
            )
            if st.button("📌 Usar esta estación (autocompletar nombre y código)"):
                st.session_state["station_name"] = fila_sel["nombre"].title()
                cod_completo = fila_sel["codigo"]
                if fila_sel["codigo_antiguo"]:
                    cod_completo += f" / {fila_sel['codigo_antiguo']}"
                st.session_state["station_code"] = cod_completo
                st.rerun()

        with st.expander("Ver tabla de estaciones filtradas"):
            tabla_estaciones = (
                df_map[["nombre", "codigo", "codigo_antiguo", "tipo", "categoria_desc", "estado_desc", "lat", "lon"]]
                .rename(columns={
                    "nombre": "Nombre", "codigo": "Código", "codigo_antiguo": "Código antiguo",
                    "tipo": "Tipo", "categoria_desc": "Categoría", "estado_desc": "Condición",
                    "lat": "Latitud", "lon": "Longitud",
                })
                .sort_values("Nombre")
            )
            st.dataframe(tabla_estaciones, use_container_width=True, hide_index=True, height=280)
            st.download_button(
                "⬇️ Descargar esta lista de estaciones (CSV)",
                tabla_estaciones.to_csv(index=False).encode("utf-8-sig"),
                file_name="estaciones_senamhi.csv",
                mime="text/csv",
            )

col_meta1, col_meta2 = st.columns(2)
with col_meta1:
    nombre_estacion = st.text_input("Nombre de la estación", st.session_state.get("station_name", ""))
with col_meta2:
    codigo_estacion = st.text_input("Código SENAMHI", st.session_state.get("station_code", ""))

if st.button("🧪 Cargar datos de ejemplo (Estación Bagua Chica, SENAMHI 1998-2024)"):
    anios = list(range(1998, 2020)) + [2022, 2023, 2024]
    p24h = [38.90, 35.70, 36.80, 77.20, 41.70, 65.70, 124.30, 62.80, 42.20, 57.90, 57.80,
            42.90, 40.10, 64.50, 56.10, 57.10, 32.90, 31.40, 33.70, 72.20, 45.30, 34.30,
            54.20, 97.40, 30.10]
    st.session_state["station_data"] = pd.DataFrame({"Año": anios, "P24h": p24h})
    st.session_state["station_name"] = "Bagua Chica"
    st.session_state["station_code"] = "000253 / DZ-02"
    st.session_state.pop("datos_mensuales", None)
    st.rerun()

tab1, tab_pdf, tab2, tab3 = st.tabs(
    [
        "📄 Importar archivo (Año, Pmax24h)",
        "📑 Importar PDF (SENAMHI)",
        "🗓️ Importar tabla mensual (SENAMHI)",
        "⌨️ Ingreso manual",
    ]
)

df_result = st.session_state.get("station_data")

with tab1:
    st.caption("Archivo CSV/Excel con dos columnas: Año y precipitación máxima en 24h (mm).")
    up = st.file_uploader("Sube el archivo", type=["csv", "xlsx", "xls"], key="up_simple")
    if up is not None:
        try:
            raw = pd.read_csv(up) if up.name.endswith("csv") else pd.read_excel(up)
            cols_lower = {c: str(c).strip().lower() for c in raw.columns}
            col_anio = next((c for c, l in cols_lower.items() if "año" in l or "ano" in l or "year" in l), None)
            col_p = next(
                (c for c, l in cols_lower.items() if "pp" in l or "precip" in l or "p24" in l or "max" in l),
                None,
            )
            if col_anio is None or col_p is None:
                st.warning("No se detectaron columnas de Año/Precipitación automáticamente. Selecciónalas:")
                col_anio = st.selectbox("Columna de Año", raw.columns, key="sel_anio")
                col_p = st.selectbox("Columna de Pmax24h", raw.columns, key="sel_p")
            df_result = raw[[col_anio, col_p]].rename(columns={col_anio: "Año", col_p: "P24h"})
            df_result = df_result.dropna()
            df_result["Año"] = df_result["Año"].astype(int)
            df_result["P24h"] = pd.to_numeric(df_result["P24h"], errors="coerce")
            df_result = df_result.dropna().sort_values("Año").reset_index(drop=True)
            st.session_state.pop("datos_mensuales", None)
            st.success(f"{len(df_result)} años importados.")
        except Exception as exc:
            st.error(f"No se pudo leer el archivo: {exc}")

with tab_pdf:
    st.caption(
        "Sube el PDF tal como te lo entregó SENAMHI (o tu asesor). Se intenta extraer la "
        "tabla automáticamente; si el PDF no tiene tablas reconocibles (por ejemplo, es un "
        "escaneo o texto libre), se ofrece una segunda vía por texto."
    )
    up_pdf = st.file_uploader("Sube el PDF", type=["pdf"], key="up_pdf")
    estrategia = st.selectbox(
        "Estrategia de extracción de tabla",
        list(pdf_import.ESTRATEGIAS_TABLA.keys()),
        help=(
            "Si la tabla extraída trae valores desalineados o incorrectos (celdas mezcladas), "
            "prueba la estrategia 'Por texto' — funciona mejor en tablas sin bordes/líneas visibles."
        ),
    )
    if up_pdf is not None:
        try:
            tablas = pdf_import.extraer_tablas(up_pdf, pdf_import.ESTRATEGIAS_TABLA[estrategia])
        except Exception as exc:
            tablas = []
            st.error(f"No se pudo abrir el PDF: {exc}")

        if tablas:
            st.success(f"Se detectaron {len(tablas)} tabla(s) en el PDF (una serie puede venir repartida en varias páginas).")

            if len(tablas) > 1:
                combinar = st.checkbox(
                    "Combinar automáticamente todas las tablas detectadas (recomendado si tu serie "
                    "está partida en varias páginas)",
                    value=True,
                )
            else:
                combinar = False

            if combinar:
                raw = pdf_import.combinar_tablas(tablas)
                st.caption(
                    f"Tabla combinada: {raw.shape[0]} filas totales, a partir de {len(tablas)} tablas del PDF."
                )
            else:
                idx = st.selectbox(
                    "Tabla a usar",
                    range(len(tablas)),
                    format_func=lambda i: f"Tabla {i + 1} (página {tablas[i].attrs.get('pagina', '?')}, "
                    f"{tablas[i].shape[0]} filas x {tablas[i].shape[1]} cols)",
                )
                raw = tablas[idx]

            st.caption(
                "⚠️ Revisa la tabla extraída: la lectura automática de PDF a veces desalinea o "
                "confunde algún valor (por ejemplo, una celda de un mes). **Puedes corregir "
                "cualquier celda haciendo doble clic sobre ella** antes de continuar."
            )
            editor_key = f"pdf_raw_editor_{up_pdf.name}_{raw.shape[0]}_{raw.shape[1]}"
            raw = st.data_editor(raw, use_container_width=True, height=220, key=editor_key)

            if pdf_import.es_formato_mensual(raw):
                st.info("Se detectó un formato mensual (Año + Ene..Dic). Se tomará el máximo de cada fila.")
                col_anio = st.selectbox("Columna de Año", raw.columns, key="pdf_col_anio_m")
                meses = [c for c in raw.columns if c != col_anio]
                meses_sel = st.multiselect("Columnas mensuales a considerar", meses, default=meses, key="pdf_meses")
                if meses_sel:
                    tmp = raw[[col_anio] + meses_sel].copy()
                    for m in meses_sel:
                        tmp[m] = pd.to_numeric(
                            tmp[m].astype(str).str.replace(",", ".", regex=False), errors="coerce"
                        )
                    tmp["P24h"] = tmp[meses_sel].max(axis=1)
                    tmp[col_anio] = pd.to_numeric(tmp[col_anio], errors="coerce")
                    df_result = tmp[[col_anio, "P24h"]].rename(columns={col_anio: "Año"}).dropna()
                    df_result["Año"] = df_result["Año"].astype(int)
                    df_result = (
                        df_result.drop_duplicates(subset="Año", keep="first")
                        .sort_values("Año")
                        .reset_index(drop=True)
                    )
                    mensual = tmp.dropna(subset=[col_anio]).copy()
                    mensual[col_anio] = mensual[col_anio].astype(int)
                    st.session_state["datos_mensuales"] = mensual.set_index(col_anio)[meses_sel]
                    st.success(f"{len(df_result)} años calculados desde el PDF.")
            else:
                col_anio = st.selectbox("Columna de Año", raw.columns, key="pdf_col_anio")
                col_p = st.selectbox("Columna de Pmax24h", raw.columns, key="pdf_col_p")
                tmp = raw[[col_anio, col_p]].rename(columns={col_anio: "Año", col_p: "P24h"}).copy()
                tmp["Año"] = pd.to_numeric(tmp["Año"], errors="coerce")
                tmp["P24h"] = pd.to_numeric(
                    tmp["P24h"].astype(str).str.replace(",", ".", regex=False), errors="coerce"
                )
                df_result = tmp.dropna()
                df_result["Año"] = df_result["Año"].astype(int)
                df_result = (
                    df_result.drop_duplicates(subset="Año", keep="first")
                    .sort_values("Año")
                    .reset_index(drop=True)
                )
                st.session_state.pop("datos_mensuales", None)
                st.success(f"{len(df_result)} años importados del PDF.")
        else:
            st.warning(
                "No se detectaron tablas extraíbles (puede ser un PDF escaneado como imagen). "
                "Se intenta un reconocimiento por texto:"
            )
            texto = pdf_import.extraer_texto(up_pdf)
            candidatos = pdf_import.parsear_pares_anio_valor(texto)
            if len(candidatos) > 0:
                st.caption("Pares Año/Valor detectados en el texto (revisa y corrige antes de usar):")
                candidatos_editado = st.data_editor(
                    candidatos, num_rows="dynamic", use_container_width=True, key="pdf_texto_editor"
                )
                if st.button("Usar esta tabla detectada por texto"):
                    df_result = candidatos_editado.dropna().sort_values("Año").reset_index(drop=True)
                    st.session_state.pop("datos_mensuales", None)
            else:
                st.error(
                    "No se pudo reconocer una serie Año/Precipitación en el texto del PDF. "
                    "Es probable que sea un PDF escaneado (imagen). Revisa el texto extraído abajo "
                    "y copia/pega manualmente los valores en la pestaña **⌨️ Ingreso manual**."
                )
            with st.expander("Ver texto extraído del PDF (para copiar manualmente)"):
                st.text_area("Texto", texto, height=250)

with tab2:
    st.caption(
        "Tabla con columna de Año y columnas mensuales (Ene..Dic) con la precipitación "
        "máxima diaria de cada mes — formato típico de exportación de SENAMHI. Se toma "
        "el máximo de cada fila como Pmax24h anual."
    )
    up2 = st.file_uploader("Sube el archivo", type=["csv", "xlsx", "xls"], key="up_mensual")
    if up2 is not None:
        try:
            raw = pd.read_csv(up2) if up2.name.endswith("csv") else pd.read_excel(up2)
            cols_lower = {c: str(c).strip().lower() for c in raw.columns}
            col_anio = next((c for c, l in cols_lower.items() if "año" in l or "ano" in l or "year" in l), raw.columns[0])
            meses = [c for c in raw.columns if c != col_anio]
            st.dataframe(raw, use_container_width=True, height=200)
            meses_sel = st.multiselect("Columnas mensuales a considerar", meses, default=meses)
            if meses_sel:
                tmp = raw[[col_anio] + meses_sel].copy()
                for m in meses_sel:
                    tmp[m] = pd.to_numeric(tmp[m], errors="coerce")
                tmp["P24h"] = tmp[meses_sel].max(axis=1)
                df_result = tmp[[col_anio, "P24h"]].rename(columns={col_anio: "Año"}).dropna()
                df_result["Año"] = df_result["Año"].astype(int)
                df_result = df_result.sort_values("Año").reset_index(drop=True)
                mensual = tmp.dropna(subset=[col_anio]).copy()
                mensual[col_anio] = mensual[col_anio].astype(int)
                st.session_state["datos_mensuales"] = mensual.set_index(col_anio)[meses_sel]
                st.success(f"{len(df_result)} años calculados (máximo mensual → anual).")
        except Exception as exc:
            st.error(f"No se pudo leer el archivo: {exc}")

with tab3:
    st.caption("Escribe o pega directamente la serie anual.")
    base = df_result if df_result is not None else pd.DataFrame({"Año": [], "P24h": []})
    edited = st.data_editor(
        base, num_rows="dynamic", use_container_width=True, key="editor_manual",
        column_config={
            "Año": st.column_config.NumberColumn(format="%d"),
            "P24h": st.column_config.NumberColumn(format="%.2f mm"),
        },
    )
    if st.button("Usar esta tabla"):
        df_result = edited.dropna().sort_values("Año").reset_index(drop=True)
        st.session_state.pop("datos_mensuales", None)

if df_result is not None and len(df_result) > 0:
    st.session_state["station_data"] = df_result
    st.session_state["station_name"] = nombre_estacion
    st.session_state["station_code"] = codigo_estacion

    st.divider()
    st.subheader("Serie de Pmax24h")
    c1, c2 = st.columns([2, 1])
    with c1:
        fig = px.bar(df_result, x="Año", y="P24h", labels={"P24h": "Pmax24h (mm)"})
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.dataframe(df_result, use_container_width=True, height=350)
        st.metric("N° de años", len(df_result))
        st.metric("Promedio (mm)", f"{df_result['P24h'].mean():.2f}")
        st.metric("Máximo (mm)", f"{df_result['P24h'].max():.2f}")

    if len(df_result) < 25:
        st.warning(
            f"Tienes {len(df_result)} años de registro. El Manual MTC recomienda un "
            "mínimo de 25 años; con menos datos el análisis de frecuencias es menos confiable."
        )

    def _generar_excel_serie(df_anual, datos_mensuales, nombre_est, codigo_est):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            workbook = writer.book
            fmt_titulo = workbook.add_format({"bold": True, "font_size": 13})
            fmt_subtitulo = workbook.add_format({"italic": True, "font_color": "#555555"})
            fmt_header = workbook.add_format({
                "bold": True, "bg_color": "#1f4e78", "font_color": "white",
                "border": 1, "align": "center",
            })
            fmt_num = workbook.add_format({"num_format": "0.00", "border": 1})
            fmt_anio = workbook.add_format({"border": 1, "align": "center"})

            hoja = "Serie anual"
            df_anual.to_excel(writer, sheet_name=hoja, startrow=3, index=False, header=False)
            ws = writer.sheets[hoja]
            ws.write(0, 0, f"Estación: {nombre_est or '(sin nombre)'}", fmt_titulo)
            ws.write(1, 0, f"Código SENAMHI: {codigo_est or '-'}", fmt_subtitulo)
            ws.write(3, 0, "Año", fmt_header)
            ws.write(3, 1, "Pmax24h (mm)", fmt_header)
            for i in range(len(df_anual)):
                ws.write(4 + i, 0, int(df_anual.iloc[i]["Año"]), fmt_anio)
                ws.write(4 + i, 1, float(df_anual.iloc[i]["P24h"]), fmt_num)
            ws.set_column(0, 0, 12)
            ws.set_column(1, 1, 16)

            if datos_mensuales is not None and len(datos_mensuales) > 0:
                hoja_m = "Datos mensuales"
                meses_cols = list(datos_mensuales.columns)
                datos_mensuales.reset_index().to_excel(writer, sheet_name=hoja_m, startrow=0, index=False)
                ws_m = writer.sheets[hoja_m]
                for col_idx in range(len(meses_cols) + 1):
                    ws_m.write(0, col_idx, datos_mensuales.reset_index().columns[col_idx], fmt_header)
                ws_m.set_column(0, 0, 12)
                ws_m.set_column(1, len(meses_cols), 12)

        return buffer.getvalue()

    excel_bytes = _generar_excel_serie(
        df_result, st.session_state.get("datos_mensuales"), nombre_estacion, codigo_estacion
    )
    st.download_button(
        "📊 Descargar serie por años (Excel)",
        excel_bytes,
        file_name=f"serie_pmax24h_{(nombre_estacion or 'estacion').strip().replace(' ', '_')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.success("Datos listos. Continúa con **📊 Análisis de frecuencias** en el menú lateral.")

    _col_sig1, _col_sig2 = st.columns([3, 1])
    with _col_sig2:
        if st.button("Análisis de frecuencias →", type="primary", use_container_width=True):
            st.switch_page("pages/2_📊_Analisis_Frecuencias.py")
else:
    st.info("Aún no hay datos cargados.")

st.sidebar.divider()
st.sidebar.caption("HIDROPro v1.0 · Creado por el Ing. Daniel Oliden")
