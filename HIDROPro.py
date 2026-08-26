import streamlit as st

st.set_page_config(page_title="Estudio Hidrológico - MTC", page_icon="💧", layout="wide")

st.title("💧 Interfaz de Estudio Hidrológico")
st.caption("Metodología del Manual de Hidrología, Hidráulica y Drenaje del MTC (Perú)")

st.markdown(
    """
Esta interfaz reproduce el flujo completo de un estudio de hidrología vial, desde los
datos de la estación SENAMHI hasta el **caudal máximo de diseño** de cada cauce/cuenca.

### Flujo de trabajo

1. **📥 Datos de estación** — importa la serie de precipitación máxima en 24h (Pmax24h)
   descargada de SENAMHI, o ingrésala manualmente.
2. **📊 Análisis de frecuencias** — prueba de datos dudosos, ajuste de 8 distribuciones
   de probabilidad y prueba de bondad de ajuste Kolmogorov-Smirnov.
3. **⏱️ Período de retorno** — calcula el Tr de diseño según el tipo de obra
   (riesgo admisible y vida útil, Manual MTC).
4. **🌧️ Curvas IDF e Hietograma** — curvas Intensidad-Duración-Frecuencia
   (Dyck-Peschke / regresión tipo Bell) e hietograma de diseño (bloque alterno).
5. **🗺️ Cuencas** — ingresa aquí tus **datos topográficos** (área, perímetro,
   longitud y pendiente del cauce, número de curva CN) por cada cuenca/subcuenca.
6. **📈 Caudal de diseño** — calcula el caudal máximo por el Método del Número de
   Curva SCS (hidrograma unitario triangular de Mockus) y el Método Racional,
   y obtiene el cuadro resumen final.

Usa el menú de la izquierda para navegar entre los pasos. Los datos se mantienen
en memoria mientras la sesión esté abierta.
"""
)

with st.expander("⚠️ Sobre los datos de SENAMHI"):
    st.markdown(
        """
SENAMHI no ofrece una API pública para series históricas: hay que **registrarse
en su portal** (senamhi.gob.pe) y descargar el archivo de tu estación (TXT/CSV/XLSX).
Esta interfaz no automatiza ese login (requiere contraseña personal); en el paso
**Datos de estación** solo importa el archivo que tú ya descargaste, o te permite
tipear la serie manualmente.
"""
    )
