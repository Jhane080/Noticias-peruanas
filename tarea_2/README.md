# Tarea 2 – Voces y documentos peruanos: del archivo escaneado al texto buscable

**Pregunta:** ¿podemos convertir documentos escaneados y entrevistas en audio en un archivo de texto estructurado y buscable?

**Dashboard público:** {{URL_STREAMLIT}}

**Respuesta corta:** {{RESPUESTA_CORTA}}

## Corpus y fuentes

Extracción: **25 de octubre de 2026**. Todo el material tiene licencia libre; la atribución de cada archivo está en [`datos/fuentes.csv`](datos/fuentes.csv) (enlace a Commons por `curid`, licencia y forma de recuperarlo).

| Corpus | Qué es | Fuente y licencia |
| :--- | :--- | :--- |
| **A. Documentos** (25) | 8 impresos (Constituciones de 1856 y 1860, guía de la Exposición de Lima de 1869, *Mercurio Peruano* de 1791, Ricardo Palma, Boletín de la Sociedad Geográfica de Lima…), 8 fotos de celular de placas en Lima y 9 manuscritos (Guaman Poma, relaciones de gobierno del siglo XVIII, mapa de Yauyos de 1856…) | Wikimedia Commons: dominio público, CC0, CC BY 4.0, CC BY-SA 3.0 y 4.0 |
| **B. Audio** ({{MINUTOS}} min, 23 clips) | 10 entrevistas reales en español grabadas en el Perú (calle, marchas, estudiantes de San Marcos) + 12 clips de español peruano leído + 1 entrevista simulada de dos voces | Wikimedia Commons (CC BY-SA 4.0) y OpenSLR 73 de Google (CC BY-SA 4.0) |
| Bonificación | 1 entrevista en quechua de Huaylas (Shansha, Áncash) | Wikimedia Commons (CC BY-SA 4.0) |

Se descartaron y reemplazaron {{DESCARTES}}. No se usaron grabaciones propias ni texto sintético.

## Pipeline

| Paso | Herramienta | Archivo |
| :--- | :--- | :--- |
| Descarga respetuosa (User-Agent, pausa de 1,5 s) | API de Commons, lectura parcial del zip de OpenSLR | `descargar.py` |
| OCR | PaddleOCR 3.7 (`lang="es"`), CPU | `procesar.py`, `01_extraccion.ipynb` |
| ASR | faster-whisper `small` (int8, CPU) con VAD Silero | `procesar.py`, `voz.py` (Sesión 13) |
| Diarización | huellas de voz WeSpeaker + clustering jerárquico | `voz.diarizar` |
| Seudonimización | lista de personas privadas + comparación difusa (rapidfuzz) + reglas de DNI/teléfono + revisión humana | `procesar.seudonimizar_texto` |
| Evaluación | CER/WER con `jiwer` contra referencias manuales; EasyOCR y Parakeet TDT 0.6B v3 como alternativas | `02_evaluacion.ipynb` |
| Extracción estructurada | Gemini 3.5 Flash-Lite con esquema JSON fijo + auditoría humana de 20 casos | `02_evaluacion.ipynb` |
| Dashboard | Streamlit + Plotly, solo lee CSV | `app.py` |

## Resultados (10 documentos y 10 clips de evaluación)

{{TABLA_RESULTADOS}}

## Hallazgos

{{HALLAZGOS}}

## Limitaciones

{{LIMITACIONES}}

## Ética y datos personales

- **Seudonimización:** se reemplazan los nombres de personas privadas que hablan o son nombradas en las entrevistas (`[PERSONA_n]`, `[ENTREVISTADOR]`). Se mantienen los nombres de figuras históricas y autoridades que aparecen en monumentos y documentos públicos. Se aplicó también a las referencias manuales antes de publicarlas.
- **Audios en el dashboard:** solo se publican los clips de OpenSLR 73 (frases leídas, sin datos personales). Las entrevistas en las que se dicen nombres se muestran como texto seudonimizado, sin audio.
- **Imágenes:** todas tienen licencia que permite redistribuirlas y no muestran datos personales. Se descartó una foto de un evento con personas.
- **Referencias manuales:** {{NOTA_REFERENCIAS}}
- La clave de la API de Gemini está en `.env`, que no se sube (ver `.env.example`).

## Cómo ejecutarlo

Dashboard (solo necesita `requirements.txt`):

```bash
cd tarea_2
pip install -r requirements.txt
streamlit run app.py
```

Notebooks (Python 3.12, Windows, CPU; los modelos pesan unos 5 GB en total):

```bash
cd tarea_2
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements-notebooks.txt
.venv/Scripts/python.exe descargar.py              # baja el corpus a datos/raw/
.venv/Scripts/python.exe procesar.py ocr           # PaddleOCR, ~1 min por página
.venv/Scripts/python.exe procesar.py asr           # faster-whisper small
.venv/Scripts/python.exe -m jupyter nbconvert --to notebook --execute --inplace 01_extraccion.ipynb
.venv/Scripts/python.exe -m jupyter nbconvert --to notebook --execute --inplace 02_evaluacion.ipynb
```

## Estructura

```
tarea_2/
├── 01_extraccion.ipynb      # OCR, ASR, diarización, seudonimización, limpieza y EDA
├── 02_evaluacion.ipynb      # CER/WER, modelos alternativos, LLM y auditoría
├── app.py                   # dashboard de Streamlit
├── descargar.py             # recupera el corpus desde Commons y OpenSLR
├── procesar.py              # OCR/ASR por lotes con respaldo en disco y seudonimización
├── voz.py                   # herramientas de audio de la Sesión 13
├── requirements.txt         # solo para la app
├── requirements-notebooks.txt
├── datos/
│   ├── documentos.csv, transcripciones.csv, extraccion_llm.csv, fuentes.csv
│   ├── auditoria_llm.csv, evaluacion_documentos.csv, evaluacion_audio.csv
│   ├── referencias/         # transcripciones manuales de la muestra de evaluación
│   └── ejemplos/            # imágenes y audios publicables para el dashboard
├── modelos/metricas.json
└── evidencias_ia/           # capturas de la conversación con Claude Code
```
