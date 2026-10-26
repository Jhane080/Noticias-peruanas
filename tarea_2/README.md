# Tarea 2 – Voces y documentos peruanos: del archivo escaneado al texto buscable

**Pregunta:** ¿podemos convertir documentos escaneados y entrevistas en audio en un archivo de texto estructurado y buscable?

**Dashboard público:** _(pendiente: se agrega al publicar en Streamlit Community Cloud)_

**Respuesta corta:** sí para impresos, fotos legibles y audio en condiciones normales (CER 0,02–0,07; WER 0,03–0,07), con revisión humana ligera. Todavía no para manuscritos coloniales (CER 0,45) ni para entrevistas con ruido de calle (WER ~0,30).

## Corpus y fuentes

Extracción: **25 de octubre de 2026**. Todo el material tiene licencia libre; la atribución de cada archivo está en [`datos/fuentes.csv`](datos/fuentes.csv) (enlace a Commons por `curid`, licencia y forma de recuperarlo).

| Corpus | Qué es | Fuente y licencia |
| :--- | :--- | :--- |
| **A. Documentos** (25) | 8 impresos (Constituciones de 1856 y 1860, guía de la Exposición de Lima de 1869, *Mercurio Peruano* de 1791, Ricardo Palma, Boletín de la Sociedad Geográfica de Lima…), 8 fotos de celular de placas en Lima y 9 manuscritos (Guaman Poma, relaciones de gobierno del siglo XVIII, mapa de Yauyos de 1856…) | Wikimedia Commons: dominio público, CC0, CC BY 4.0, CC BY-SA 3.0 y 4.0 |
| **B. Audio** (38,4 min, 23 clips) | 10 entrevistas reales en español grabadas en el Perú (calle, marchas, estudiantes de San Marcos) + 12 clips de español peruano leído + 1 entrevista simulada de dos voces | Wikimedia Commons (CC BY-SA 4.0) y OpenSLR 73 de Google (CC BY-SA 4.0) |
| Bonificación | 1 entrevista en quechua de Huaylas (Shansha, Áncash) | Wikimedia Commons (CC BY-SA 4.0) |

Se descartaron y reemplazaron 7 documentos: 6 ilegibles (menos de 40 caracteres o confianza media del OCR menor a 0,60) y 1 foto que no era un documento (un evento con personas). Ningún audio se descartó (todos tienen voz en más del 20 % de su duración). No hubo duplicados por hash. No se usaron grabaciones propias ni texto sintético.

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

| Modalidad | Modelo | Métrica | Valor | Latencia (CPU) |
| :--- | :--- | :--- | ---: | :--- |
| Documentos | **PaddleOCR 3.7** (base) | CER | **0,056** | ~33 s por página |
| Documentos | EasyOCR 1.7 | CER | 0,168 | ~25 s por página |
| Audio | faster-whisper `small` (base) | WER | 0,212 | RTF 0,24 |
| Audio | **Parakeet TDT 0.6B v3** | WER | **0,189** | RTF 0,35 |
| Campos con LLM | Gemini 3.5 Flash-Lite | Acuerdo con auditoría humana | **15/20 (75 %)** | — |

| CER por tipo | PaddleOCR | EasyOCR | | WER por condición | Whisper small | Parakeet |
| :--- | ---: | ---: | --- | :--- | ---: | ---: |
| Impreso (3) | 0,015 | 0,104 | | Leído en estudio (6) | 0,070 | 0,029 |
| Foto (4) | 0,067 | 0,226 | | Dos voces alternadas (1) | 0,063 | 0,051 |
| Manuscrito (3) | 0,446 | 0,651 | | Entrevista real (3) | 0,308 | 0,292 |

## Hallazgos

1. **El tipo de documento pesa más que el modelo.** PaddleOCR se equivoca en 1,5 de cada 100 caracteres en un impreso del siglo XIX, pero en casi 45 de cada 100 en un manuscrito colonial. EasyOCR es peor en todos los tipos, pero sigue el mismo orden. Para manuscritos haría falta un modelo de escritura a mano (HTR) entrenado en paleografía hispana.
2. **El ruido de la calle iguala a los modelos.** Con español leído, Parakeet comete menos de la mitad de errores que Whisper small (0,029 frente a 0,070). En las entrevistas reales los dos quedan cerca de 0,30. Whisper además "corrige" el habla coloquial: escribe "pero es un resultado" donde se dijo "pues, esperando el resultado nomás". Suena bien, pero no es lo que se dijo.
3. **El LLM le busca sentido a todo.** 3 de sus 5 errores en la auditoría fueron resumir como una conversación unas frases leídas que no tienen relación entre sí. Los otros 2 fueron llenar `fecha` y `monto` con un año mencionado de pasada y con un número que era ruido del OCR.

## Limitaciones

1. **Muestra de evaluación chica:** 10 documentos y 10 clips (7,3 minutos). Un solo documento difícil mueve bastante el CER global. Las cifras sirven para comparar modelos, no como precisión garantizada.
2. **Referencias y diarización imperfectas:** el borrador de las referencias de documentos lo escribió un asistente de IA mirando las imágenes, y la autora lo corrigió (además se le agregó una línea omitida a `doc_014`). La diarización automática creó un tercer hablante inexistente en una entrevista de Huancayo por un tramo de dos palabras.
3. **Solo CPU:** PaddleOCR tarda ~1 minuto por página y Parakeet no se pudo usar en todo el corpus. La app no corre modelos en vivo: muestra resultados ya calculados.

## Ética y datos personales

- **Seudonimización:** se reemplazan los nombres de personas privadas que hablan o son nombradas en las entrevistas (`[PERSONA_n]`, `[ENTREVISTADOR]`). Se mantienen los nombres de figuras históricas y autoridades que aparecen en monumentos y documentos públicos. Se aplicó también a las referencias manuales antes de publicarlas.
- **Audios en el dashboard:** solo se publican los clips de OpenSLR 73 (frases leídas, sin datos personales). Las entrevistas en las que se dicen nombres se muestran como texto seudonimizado, sin audio.
- **Imágenes:** todas tienen licencia que permite redistribuirlas y no muestran datos personales. Se descartó una foto de un evento con personas.
- **Referencias manuales:** los documentos tienen un borrador escrito por Claude (asistente de IA) mirando cada imagen, sin pasar por los OCR evaluados, que la autora corrigió contra la imagen. Las entrevistas de Commons las transcribió la autora de oído; después, a pedido de ella, Claude corrigió 19 erratas de tipeo. Los clips de OpenSLR usan la transcripción oficial del dataset, hecha por personas.
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
