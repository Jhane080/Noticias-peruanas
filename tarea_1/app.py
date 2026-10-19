"""Dashboard de la Tarea 1: ¿pueden convertir titulares peruanos en un clasificador de noticias?

Para correrlo (desde la carpeta tarea_1/):
    streamlit run app.py
"""

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from transformers import pipeline

CARPETA = Path(__file__).parent
CARPETA_MODELO = CARPETA / "modelo"

st.set_page_config(page_title="Clasificador de titulares peruanos", page_icon="🗞️", layout="wide")


@st.cache_data
def cargar_noticias():
    return pd.read_csv(CARPETA / "datos" / "noticias.csv", dtype=str)


@st.cache_data
def cargar_metricas():
    with open(CARPETA_MODELO / "metricas.json", encoding="utf-8") as archivo:
        return json.load(archivo)


# el modelo pesa ~540 MB: se carga una sola vez y queda en memoria
@st.cache_resource
def cargar_clasificador():
    return pipeline("text-classification", model=str(CARPETA_MODELO), tokenizer=str(CARPETA_MODELO), top_k=None)


noticias = cargar_noticias()
metricas = cargar_metricas()

# --- Encabezado ---
st.title("🗞️ ¿Pueden convertirse los titulares peruanos en un clasificador de noticias?")
st.markdown(
    f"""
Recolectamos **{len(noticias)} titulares de El Comercio** (18 de octubre de 2026) desde sus
sitemaps oficiales y los agrupamos en 4 categorías: política, economía, deportes y
ciencia/tecnología. Un LLM (**{metricas['modelo_llm']}**) etiquetó todo el dataset y esas etiquetas
sirvieron para entrenar un **DistilBERT multilingüe**, que se evaluó en un test reservado
de {metricas['noticias_test']} noticias.
"""
)

# --- Filtros ---
st.sidebar.header("Filtros")
medios = sorted(noticias["medio"].unique())
medios_elegidos = st.sidebar.multiselect("Medio", medios, default=medios)
categorias = sorted(noticias["etiqueta"].unique())
categorias_elegidas = st.sidebar.multiselect("Categoría", categorias, default=categorias)

noticias_filtradas = noticias[
    noticias["medio"].isin(medios_elegidos) & noticias["etiqueta"].isin(categorias_elegidas)
]

# --- Indicadores ---
columna_1, columna_2, columna_3 = st.columns(3)
columna_1.metric("Noticias recolectadas", len(noticias), f"{len(noticias_filtradas)} con los filtros", delta_color="off")
columna_2.metric("F1 macro en test", f"{metricas['f1_macro_test']:.2f}", f"zero-shot: {metricas['f1_zero_shot_40']:.2f}", delta_color="off")
columna_3.metric("Acuerdo LLM vs. auditoría humana", f"{metricas['porcentaje_acuerdo']:.0f}%", metricas["acuerdo_llm_humano"], delta_color="off")

# --- Gráfico y tabla ---
st.subheader("Distribución de categorías")
conteo = noticias_filtradas["etiqueta"].value_counts().reset_index()
conteo.columns = ["categoria", "noticias"]
grafico = px.bar(conteo, x="categoria", y="noticias", text="noticias", color="categoria",
                 labels={"categoria": "Categoría", "noticias": "Número de noticias"})
grafico.update_layout(showlegend=False)
st.plotly_chart(grafico, use_container_width=True)

st.subheader("Noticias")
columnas_tabla = ["fecha", "etiqueta", "titular", "bajada", "seccion_original", "url"]
st.dataframe(noticias_filtradas[columnas_tabla], use_container_width=True, hide_index=True)
st.download_button(
    "Descargar CSV filtrado",
    noticias_filtradas.to_csv(index=False).encode("utf-8"),
    file_name="noticias_filtradas.csv",
    mime="text/csv",
)

# --- Probador en vivo ---
st.divider()
st.subheader("🔮 Probador en vivo")
titular_nuevo = st.text_input("Escribe o pega un titular", placeholder="Ej.: BCR mantiene su tasa de referencia en 4.25%")

if st.button("Clasificar", type="primary"):
    if titular_nuevo.strip() == "":
        st.warning("Escribe un titular primero.")
    elif not (CARPETA_MODELO / "model.safetensors").exists():
        st.error("No encuentro los pesos del modelo en modelo/. Corre primero 02_clasificacion.ipynb.")
    else:
        clasificador = cargar_clasificador()
        probabilidades = pd.DataFrame(clasificador(titular_nuevo)[0])
        probabilidades.columns = ["categoria", "probabilidad"]
        ganadora = probabilidades.iloc[0]
        st.success(f"Categoría predicha: **{ganadora['categoria']}** · probabilidad {ganadora['probabilidad']:.1%}")
        grafico_probabilidades = px.bar(
            probabilidades, x="probabilidad", y="categoria", orientation="h",
            range_x=[0, 1], text_auto=".1%", labels={"probabilidad": "Probabilidad", "categoria": ""},
        )
        st.plotly_chart(grafico_probabilidades, use_container_width=True)
