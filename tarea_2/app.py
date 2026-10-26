"""Dashboard de la Tarea 2: documentos y voces peruanas convertidos en texto buscable.

    streamlit run app.py

Solo lee los CSV y JSON que dejaron los notebooks: no corre OCR, ASR ni LLM en el servidor.
"""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

CARPETA = Path(__file__).resolve().parent
DATOS = CARPETA / "datos"
EJEMPLOS = DATOS / "ejemplos"

st.set_page_config(page_title="Voces y documentos peruanos", page_icon="📜", layout="wide")


@st.cache_data
def cargar():
    documentos = pd.read_csv(DATOS / "documentos.csv")
    audios = pd.read_csv(DATOS / "transcripciones.csv")
    extraccion = pd.read_csv(DATOS / "extraccion_llm.csv")
    fuentes = pd.read_csv(DATOS / "fuentes.csv")
    eval_docs = pd.read_csv(DATOS / "evaluacion_documentos.csv")
    eval_audio = pd.read_csv(DATOS / "evaluacion_audio.csv")
    metricas = json.loads((CARPETA / "modelos" / "metricas.json").read_text(encoding="utf-8"))
    documentos = documentos.merge(fuentes[["id", "fuente_url", "licencia"]], on="id", how="left")
    audios = audios.merge(fuentes[["id", "fuente_url", "licencia"]], on="id", how="left")
    audios["fuente_corta"] = audios["fuente_url"].str.contains("openslr").map(
        {True: "OpenSLR 73 (leído)", False: "Commons (entrevista)"})
    audios["minutos"] = audios["duracion_seg"] / 60
    return documentos, audios, extraccion, eval_docs, eval_audio, metricas


documentos, audios, extraccion, eval_docs, eval_audio, metricas = cargar()
campos_llm = {fila.id: json.loads(fila.campos_json) for fila in extraccion.itertuples()}

# ─────────────────────────────────────────── encabezado
st.title("¿Podemos convertir documentos escaneados y entrevistas en audio en texto buscable?")
st.markdown(
    "Pipeline de IA sobre **25 documentos peruanos** (impresos, fotos de celular y manuscritos) y "
    f"**{audios['minutos'].sum():.0f} minutos de español hablado en el Perú**. "
    "OCR con **PaddleOCR**, transcripción con **faster-whisper** (VAD y diarización), seudonimización de "
    "personas privadas y extracción de campos con **Gemini**. Los modelos se evaluaron contra "
    "transcripciones manuales de 10 documentos y 10 clips. Fuentes: Wikimedia Commons y OpenSLR 73, "
    "con licencias libres. Datos extraídos el 25 de octubre de 2026."
)

# ─────────────────────────────────────────── filtros
with st.sidebar:
    st.header("Filtros")
    busqueda = st.text_input("Buscar en los textos (OCR y ASR)", placeholder="ej.: Lima, partido, constitución")
    tipos = st.multiselect("Tipo de documento", ["impreso", "foto", "manuscrito"], default=["impreso", "foto", "manuscrito"])
    modelo_ocr = st.radio("Modelo OCR para la evaluación", ["PaddleOCR", "EasyOCR"], horizontal=True)
    modelo_asr = st.radio("Modelo ASR para la evaluación", ["faster-whisper small", "Parakeet v3"], horizontal=True)
    fuentes_audio = st.multiselect("Fuente del audio", sorted(audios["fuente_corta"].unique()),
                                   default=sorted(audios["fuente_corta"].unique()))
    maximo = float(audios["minutos"].max())
    rango_minutos = st.slider("Duración del clip (minutos)", 0.0, round(maximo + 0.1, 1), (0.0, round(maximo + 0.1, 1)), 0.1)
    st.caption("Los filtros cambian los gráficos, las tablas y los exploradores.")

columna_cer = "cer_paddle" if modelo_ocr == "PaddleOCR" else "cer_easyocr"
columna_wer = "wer_small" if modelo_asr == "faster-whisper small" else "wer_parakeet"

docs_filtrados = documentos[documentos["tipo"].isin(tipos)]
audios_filtrados = audios[audios["fuente_corta"].isin(fuentes_audio)
                          & audios["minutos"].between(rango_minutos[0], rango_minutos[1])]
if busqueda:
    docs_filtrados = docs_filtrados[docs_filtrados["texto_ocr"].str.contains(busqueda, case=False, na=False)]
    audios_filtrados = audios_filtrados[audios_filtrados["texto_asr"].str.contains(busqueda, case=False, na=False)]

# ─────────────────────────────────────────── indicadores
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Documentos procesados", len(documentos), f"{len(docs_filtrados)} con los filtros", delta_color="off")
c2.metric("Minutos de audio transcritos", f"{audios['minutos'].sum():.1f}",
          f"{audios_filtrados['minutos'].sum():.1f} con los filtros", delta_color="off")
c3.metric(f"CER {modelo_ocr} (10 docs)", f"{metricas['cer_paddle' if modelo_ocr == 'PaddleOCR' else 'cer_easyocr']:.3f}",
          help="Errores por carácter frente a la transcripción manual. Menos es mejor.")
c4.metric(f"WER {modelo_asr} (10 clips)", f"{metricas['wer_small' if modelo_asr == 'faster-whisper small' else 'wer_parakeet']:.3f}",
          help="Errores por palabra frente a la transcripción manual. Menos es mejor.")
c5.metric("Acuerdo LLM vs. auditoría humana", f"{metricas['porcentaje_acuerdo']:.0f} %", metricas["acuerdo_llm_humano"], delta_color="off")

pestana_resumen, pestana_docs, pestana_audio, pestana_eval = st.tabs(
    ["📊 Resumen", "📜 Documentos", "🎙️ Audios", "⚖️ Evaluación de modelos"])

# ─────────────────────────────────────────── resumen
with pestana_resumen:
    izquierda, derecha = st.columns(2)
    with izquierda:
        por_tipo = docs_filtrados.assign(caracteres=docs_filtrados["texto_ocr"].str.len()).groupby("tipo").agg(
            documentos=("id", "count"), caracteres=("caracteres", "median")).reset_index()
        fig = px.bar(por_tipo, x="tipo", y="caracteres", color="tipo", text="documentos",
                     title="Mediana de caracteres que el OCR saca por documento",
                     labels={"tipo": "Tipo", "caracteres": "Caracteres (mediana)"})
        fig.update_traces(texttemplate="%{text} docs")
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, width="stretch")
    with derecha:
        fig = px.bar(audios_filtrados.sort_values("duracion_seg"), x="minutos", y="id", color="fuente_corta", orientation="h",
                     title="Duración de cada clip transcrito", labels={"minutos": "Minutos", "id": "", "fuente_corta": "Fuente"},
                     height=520)
        st.plotly_chart(fig, width="stretch")
    tema_docs = [campos_llm.get(i, {}).get("tema") for i in docs_filtrados["id"]]
    tema_audio = [campos_llm.get(i, {}).get("tema") for i in audios_filtrados["id"]]
    st.subheader("Temas que extrajo el LLM")
    st.dataframe(pd.DataFrame({"id": list(docs_filtrados["id"]) + list(audios_filtrados["id"]),
                               "tema": tema_docs + tema_audio}), width="stretch", hide_index=True, height=250)

# ─────────────────────────────────────────── documentos
with pestana_docs:
    st.subheader(f"{len(docs_filtrados)} documentos")
    tabla = docs_filtrados[["id", "tipo", "fuente", "texto_ocr", "modelo_ocr", "texto_referencia"]]
    st.dataframe(tabla, width="stretch", hide_index=True, height=260)
    st.download_button("Descargar CSV (textos revisados)", tabla.to_csv(index=False).encode("utf-8"),
                       "documentos_filtrados.csv", "text/csv")

    st.divider()
    st.subheader("Explorador de documentos")
    if docs_filtrados.empty:
        st.info("Ningún documento cumple los filtros.")
    else:
        elegido = st.selectbox("Documento", docs_filtrados["id"], format_func=lambda i: f"{i} · {documentos.set_index('id').loc[i, 'tipo']}")
        fila = documentos.set_index("id").loc[elegido]
        imagen, texto = st.columns([2, 3])
        with imagen:
            ruta_imagen = EJEMPLOS / "documentos" / f"{elegido}.jpg"
            if ruta_imagen.exists():
                st.image(str(ruta_imagen), caption=f"{fila['licencia']} · {fila['fuente_url']}")
            else:
                st.info("Imagen no publicada.")
        with texto:
            evaluado = eval_docs[eval_docs["id"] == elegido]
            if not evaluado.empty and modelo_ocr == "EasyOCR":
                st.markdown("**Texto OCR (EasyOCR)**")
                st.text(evaluado.iloc[0]["easyocr_texto"])
            else:
                st.markdown("**Texto OCR (PaddleOCR)**")
                st.text(fila["texto_ocr"])
            if not evaluado.empty:
                st.metric(f"CER {modelo_ocr}", f"{evaluado.iloc[0][columna_cer]:.3f}")
            if isinstance(fila["texto_referencia"], str):
                with st.expander("Transcripción manual de referencia"):
                    st.text(fila["texto_referencia"])
            st.markdown("**Campos extraídos por el LLM**")
            st.json(campos_llm.get(elegido, {}))

# ─────────────────────────────────────────── audios
with pestana_audio:
    st.subheader(f"{len(audios_filtrados)} clips · {audios_filtrados['minutos'].sum():.1f} minutos")
    tabla = audios_filtrados[["id", "fuente_corta", "duracion_seg", "n_hablantes", "texto_asr", "modelo_asr", "texto_referencia"]]
    st.dataframe(tabla, width="stretch", hide_index=True, height=260)
    st.download_button("Descargar CSV (transcripciones seudonimizadas)", tabla.to_csv(index=False).encode("utf-8"),
                       "transcripciones_filtradas.csv", "text/csv")

    st.divider()
    st.subheader("Explorador de audios")
    if audios_filtrados.empty:
        st.info("Ningún clip cumple los filtros.")
    else:
        elegido = st.selectbox("Clip", audios_filtrados["id"])
        fila = audios.set_index("id").loc[elegido]
        st.caption(f"{fila['duracion_seg']:.0f} s · {fila['n_hablantes']} hablante(s) detectado(s) · {fila['licencia']} · {fila['fuente_url']}")
        ruta_audio = EJEMPLOS / "audio" / f"{elegido}.mp3"
        if ruta_audio.exists():
            st.audio(str(ruta_audio))
        else:
            st.info("El audio no se publica aquí porque en él se dicen nombres de personas privadas. "
                    "La transcripción está seudonimizada.")
        st.markdown("**Transcripción (faster-whisper small, con marcas de hablante)**")
        st.write(fila["texto_asr"])
        evaluado = eval_audio[eval_audio["id"] == elegido]
        if not evaluado.empty:
            st.markdown("**Comparación de modelos en este clip**")
            uno, dos = st.columns(2)
            uno.metric("WER faster-whisper small", f"{evaluado.iloc[0]['wer_small']:.3f}")
            uno.write(evaluado.iloc[0]["small_texto"])
            dos.metric("WER Parakeet v3", f"{evaluado.iloc[0]['wer_parakeet']:.3f}")
            dos.write(evaluado.iloc[0]["parakeet_texto"])
            if isinstance(fila["texto_referencia"], str):
                with st.expander("Transcripción manual de referencia"):
                    st.write(fila["texto_referencia"])
        st.markdown("**Campos extraídos por el LLM**")
        st.json(campos_llm.get(elegido, {}))

# ─────────────────────────────────────────── evaluación
with pestana_eval:
    st.markdown("Los dos modelos de cada modalidad se compararon sobre **los mismos** 10 documentos y 10 clips, "
                "contra transcripciones manuales.")
    izquierda, derecha = st.columns(2)
    with izquierda:
        cer_tipo = pd.DataFrame(metricas["cer_por_tipo"])
        cer_tipo = cer_tipo[cer_tipo["tipo"].isin(tipos)]
        grafico = cer_tipo.melt(id_vars="tipo", value_vars=["CER PaddleOCR", "CER EasyOCR"], var_name="modelo", value_name="CER")
        fig = px.bar(grafico, x="tipo", y="CER", color="modelo", barmode="group", text_auto=".2f",
                     title="CER por tipo de documento (menos es mejor)")
        st.plotly_chart(fig, width="stretch")
    with derecha:
        grafico = eval_audio.melt(id_vars=["id", "condicion"], value_vars=["wer_small", "wer_parakeet"], var_name="modelo", value_name="WER")
        grafico["modelo"] = grafico["modelo"].map({"wer_small": "faster-whisper small", "wer_parakeet": "Parakeet v3"})
        fig = px.bar(grafico, x="id", y="WER", color="modelo", barmode="group", hover_data=["condicion"],
                     title="WER por clip (menos es mejor)")
        st.plotly_chart(fig, width="stretch")
    st.dataframe(pd.DataFrame(metricas["wer_por_condicion"]).round(3), width="stretch", hide_index=True)
    st.markdown(f"**Extracción con LLM ({metricas['modelo_llm']}):** {metricas['acuerdo_llm_humano']} extracciones "
                "completamente correctas en la auditoría humana de 20 casos al azar (10 documentos y 10 audios).")
