# Tarea 1 – Noticias peruanas: del titular al clasificador

## 1. Pregunta del proyecto

**¿Pueden convertirse los titulares peruanos en un clasificador de noticias?**

Recolectamos titulares reales de El Comercio, los etiquetamos con un LLM (supervisión débil),
entrenamos un Transformer ligero (DistilBERT multilingüe) y lo pusimos en un dashboard de
Streamlit donde cualquiera puede escribir un titular y ver la categoría predicha.

Categorías: `politica`, `economia`, `deportes`, `ciencia_tecnologia`.

## 2. Medio y fechas de extracción

| Dato | Valor |
| :--- | :--- |
| Opción | **B – El Comercio** (`elcomercio.pe`) |
| Fecha de descarga | 18 de octubre de 2026 |
| Fechas de publicación | del 6 al 18 de octubre de 2026 |
| Fuente | Sitemaps oficiales de noticias por sección (`/sitemap/news/<seccion>/`), listados en `robots.txt`, más la etiqueta `og:description` de cada noticia como bajada |
| Noticias | 402 descargadas → **383 finales** (3 URLs duplicadas y 16 fuera de las 4 categorías) |
| Buenas prácticas | `robots.txt` revisado, `User-Agent` propio, 1.5 s de pausa entre solicitudes y máximo 1 reintento |

Antes probamos con La República. Su RSS solo trae entre 7 y 21 noticias por sección y su API
interna responde `403` a clientes que no son navegadores. No forzamos el bloqueo y lo
documentamos en `01_recoleccion.ipynb`.

## 3. Resultados

Todo medido sobre el **conjunto de test reservado** (58 noticias, 15 %), contra la sección del diario.

| Modelo | Accuracy | F1 macro | Segundos por titular |
| :--- | :---: | :---: | :---: |
| Zero-shot (`Recognai/bert-base-spanish-wwm-cased-xnli`), 40 titulares | — | 0.591 | — |
| Zero-shot, test completo | 0.621 | 0.606 | 0.79 |
| LLM débil (`gemini-3.5-flash-lite`) | 0.948 | 0.946 | 0.08 (API) |
| **DistilBERT multilingüe fine-tuned** | **0.845** | **0.844** | 0.09 (CPU) |

- Acuerdo LLM vs. auditoría humana: **20/20 (100 %)**. Contra la sección del diario, el LLM coincide en el 92 %.
- Split 70/15/15 estratificado con `random_state=42`: 268 train, 57 validación, 58 test.
- Fine-tuning: 3 épocas, lote 16, mejor época por F1 macro en validación (0.856), 5 minutos en CPU.

## 4. Hallazgos analíticos

1. **Deportes es la categoría más fácil y economía la más difícil.** Deportes obtuvo F1 = 1.00
   porque su vocabulario (clubes, marcadores, "goles", "Liga 1") no se cruza con nada. Economía
   obtuvo 0.69: sus errores son noticias donde la economía se mezcla con el Estado (ONP, Indecopi,
   viceministros, obras ante El Niño) o entrevistas que empiezan con "Nombre, cargo: '...'", el
   mismo formato de las notas políticas. La frontera entre categorías no es léxica sino temática.
2. **El ritmo de publicación cambia mucho entre secciones.** Las últimas 100 noticias de deportes
   caben en 3 días, mientras que ciencia y tecnología necesita casi 2 semanas (del 6 al 18 de
   octubre). Un clasificador entrenado en una sola semana ve un deporte muy "de coyuntura" (Liga 1,
   Clausura) y una tecnología más atemporal. Además, política tiene los titulares más largos
   (mediana de 109 caracteres) porque suelen citar declaraciones textuales.

## 5. Limitaciones técnicas

1. **Muestra pequeña y de una sola fecha de corte.** 383 noticias y solo 58 en test: un error
   mueve el F1 de una categoría en unos 3 puntos. Los sitemaps solo exponen las últimas 100 notas
   por sección, así que el modelo aprendió la agenda de octubre de 2026 (nombres propios de esa
   semana) y puede perder precisión con otras coyunturas. Lo ideal sería recolectar durante varias
   semanas.
2. **Etiquetas débiles y dependencia de la API.** El modelo aprendió de las etiquetas de Gemini,
   que coinciden con el diario en el 92 %; ese ruido pasa al modelo (en 2 de sus 9 errores Gemini
   también se equivocaba). Además, el plan gratuito de Gemini permite solo 20 solicitudes diarias
   por modelo y devolvió errores 503 por alta demanda: tuvimos que agrupar 50 titulares por
   solicitud y cambiar a `gemini-3.5-flash-lite`. Los pesos del modelo (541 MB) no caben en GitHub,
   así que el dashboard no se desplegó en Streamlit Cloud; se ejecuta en local.

## 6. Cómo ejecutarlo en local

Desde la carpeta `tarea_1/`:

```bash
# 1. Crear un entorno e instalar dependencias
python -m venv .venv
.venv\Scripts\activate          # en Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt

# 2. (Solo si se quiere re-etiquetar con Gemini) poner la clave en .env
copy .env.example .env          # y pegar GEMINI_API_KEY

# 3. Ejecutar los notebooks en orden
jupyter nbconvert --to notebook --execute --inplace 01_recoleccion.ipynb
jupyter nbconvert --to notebook --execute --inplace 02_clasificacion.ipynb

# 4. Levantar el dashboard
streamlit run app.py
```

Los pesos del modelo (`modelo/model.safetensors`, ~540 MB) **no están en GitHub** porque superan
el límite de 100 MB. Se generan al correr `02_clasificacion.ipynb` (unos minutos en CPU). Los
respaldos crudos (`datos/raw/`) y las etiquetas del LLM (`datos/etiquetas_llm.csv`) sí están en
el repositorio, así que los notebooks se pueden volver a correr sin volver a scrapear ni llamar a
la API.

## Estructura

```text
tarea_1/
├── 01_recoleccion.ipynb       # Scraping, limpieza y EDA
├── 02_clasificacion.ipynb     # Zero-shot, LLM, fine-tuning y evaluación
├── app.py                     # Dashboard de Streamlit
├── requirements.txt
├── README.md
├── .gitignore
├── .env.example
├── datos/
│   ├── noticias.csv           # 383 noticias, 7 columnas
│   ├── etiquetas_llm.csv      # etiquetas de Gemini
│   ├── auditoria_humana.csv   # revisión manual de 20 etiquetas
│   └── raw/                   # sitemaps y bajadas tal como se descargaron
└── modelo/
    ├── config.json, tokenizer*  # artefactos ligeros
    └── metricas.json            # métricas que lee el dashboard
```
