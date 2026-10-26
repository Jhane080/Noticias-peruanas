"""OCR y transcripción por lotes, con respaldo en disco.

Los modelos tardan (PaddleOCR ~40 s por página en CPU), así que cada resultado se guarda
apenas sale: si el proceso se corta, al volver a correrlo retoma donde se quedó. Los
notebooks llaman a estas mismas funciones; si el respaldo ya existe, lo leen sin
volver a correr el modelo.

    .venv\\Scripts\\python.exe procesar.py ocr        # los 28 documentos con PaddleOCR
    .venv\\Scripts\\python.exe procesar.py asr        # todos los audios con faster-whisper small
"""
import torch  # noqa: F401  en Windows hay que cargar torch antes que paddle o choca una DLL

import json
import sys
import time
from pathlib import Path

import pandas as pd
from PIL import Image

RAIZ = Path(__file__).resolve().parent
DOCUMENTOS = RAIZ / "datos" / "raw" / "documentos"
AUDIO = RAIZ / "datos" / "raw" / "audio"
LADO_MAXIMO = 2000  # las fotos de celular vienen a 4000 px: a 2000 el OCR tarda la mitad y lee igual

_motores = {}


def preparar_imagen(ruta):
    """Copia reducida (lado mayor de 2000 px, RGB) que es la que se le pasa a los dos OCR."""
    destino = DOCUMENTOS / "preparadas" / (Path(ruta).stem + ".jpg")
    if not destino.exists():
        destino.parent.mkdir(parents=True, exist_ok=True)
        imagen = Image.open(ruta).convert("RGB")
        imagen.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
        imagen.save(destino, quality=92)
    return destino


def ocr(ruta, motor="paddle"):
    """Texto de una imagen con PaddleOCR o EasyOCR. Guarda el JSON crudo con cada línea y su confianza."""
    ruta = Path(ruta)
    respaldo = DOCUMENTOS / f"ocr_{motor}" / f"{ruta.stem}.json"
    if respaldo.exists():
        return json.loads(respaldo.read_text(encoding="utf-8"))
    respaldo.parent.mkdir(parents=True, exist_ok=True)
    imagen = preparar_imagen(ruta)
    inicio = time.perf_counter()
    if motor == "paddle":
        if "paddle" not in _motores:
            from paddleocr import PaddleOCR
            _motores["paddle"] = PaddleOCR(lang="es", use_doc_orientation_classify=False,
                                           use_doc_unwarping=False, use_textline_orientation=False)
        resultado = _motores["paddle"].predict(str(imagen))[0]
        lineas = list(resultado["rec_texts"])
        confianzas = [float(c) for c in resultado["rec_scores"]]
        # guardamos el recorte de cada línea detectada: sirve para revisar a mano qué leyó mal el modelo
        recortes = respaldo.parent / "recortes" / ruta.stem
        recortes.mkdir(parents=True, exist_ok=True)
        pagina = Image.open(imagen)
        for n, poligono in enumerate(resultado["rec_polys"]):
            xs, ys = [p[0] for p in poligono], [p[1] for p in poligono]
            pagina.crop((min(xs), min(ys), max(xs), max(ys))).save(recortes / f"linea_{n:03d}.png")
    else:
        if "easyocr" not in _motores:
            import easyocr
            _motores["easyocr"] = easyocr.Reader(["es"], gpu=False, verbose=False)
        # paragraph=False devuelve línea por línea, igual que PaddleOCR
        resultado = _motores["easyocr"].readtext(str(imagen), paragraph=False)
        lineas = [texto for _, texto, _ in resultado]
        confianzas = [float(c) for _, _, c in resultado]
    salida = {"id": ruta.stem, "motor": motor, "lineas": lineas, "confianzas": confianzas,
              "texto": "\n".join(lineas), "segundos": round(time.perf_counter() - inicio, 2)}
    respaldo.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    return salida


def transcribir(ruta, modelo="small", idioma="es"):
    """Segmentos con tiempo de un audio. faster-whisper con VAD; Parakeet a través de voz.py."""
    import voz
    ruta = Path(ruta)
    respaldo = AUDIO / f"asr_{modelo}" / f"{ruta.stem}.json"
    if respaldo.exists():
        return json.loads(respaldo.read_text(encoding="utf-8"))
    respaldo.parent.mkdir(parents=True, exist_ok=True)
    audio = voz.cargar_audio(ruta)
    if modelo not in _motores:
        if modelo in ("small", "large-v3-turbo"):
            from faster_whisper import WhisperModel
            nombre = "small" if modelo == "small" else "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
            _motores[modelo] = WhisperModel(nombre, device="cpu", compute_type="int8", cpu_threads=4)
        else:
            _motores[modelo] = voz.Transcriptor(modelo, device="cpu")
    inicio = time.perf_counter()
    if modelo in ("small", "large-v3-turbo"):
        # vad_filter: no le pasamos silencios ni música al modelo, que es donde Whisper inventa frases
        segmentos, _ = _motores[modelo].transcribe(audio, language=idioma, beam_size=5, vad_filter=True,
                                                   vad_parameters={"min_silence_duration_ms": 300},
                                                   condition_on_previous_text=False)
        segmentos = [voz.Segmento(round(s.start, 2), round(s.end, 2), s.text.strip()) for s in segmentos]
    else:
        segmentos = _motores[modelo].segmentos(audio, idioma=idioma)
    segundos = time.perf_counter() - inicio
    salida = {"id": ruta.stem, "modelo": modelo, "duracion_seg": round(len(audio) / voz.SR, 2),
              "segundos_proceso": round(segundos, 2),
              "segmentos": [{"inicio": s.inicio, "fin": s.fin, "texto": s.texto} for s in segmentos]}
    respaldo.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    return salida


def diarizar(ruta, modelo="small", n_hablantes=None):
    """Agrega el hablante (H1, H2...) a cada segmento ya transcrito. Usa las huellas de voz de voz.py."""
    import voz
    ruta = Path(ruta)
    respaldo = AUDIO / f"diarizacion_{modelo}" / f"{ruta.stem}.json"
    if respaldo.exists():
        return json.loads(respaldo.read_text(encoding="utf-8"))
    respaldo.parent.mkdir(parents=True, exist_ok=True)
    transcripcion = transcribir(ruta, modelo)
    segmentos = [voz.Segmento(s["inicio"], s["fin"], s["texto"]) for s in transcripcion["segmentos"]]
    con_hablante = voz.diarizar(voz.cargar_audio(ruta), segmentos, n_hablantes=n_hablantes, device="cpu")
    salida = {**transcripcion, "segmentos": [{"inicio": s.inicio, "fin": s.fin, "texto": s.texto, "hablante": s.hablante}
                                             for s in con_hablante]}
    respaldo.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    # también en los formatos que abren VLC, ELAN o Atlas.ti
    (respaldo.with_suffix(".srt")).write_text(voz.a_srt(con_hablante), encoding="utf-8")
    (respaldo.with_suffix(".txt")).write_text(voz.a_texto(con_hablante), encoding="utf-8")
    return salida


# Personas privadas que hablan o son nombradas en las entrevistas de Commons. Primero el nombre
# completo, después el apellido solo: el ASR escribe "Básquez", "sabarrientos", "Rientos"...
# y la comparación difusa los atrapa igual.
REEMPLAZOS_DIFUSOS = {
    "Elena Durán": "[PERSONA_1]", "Isabel Vásquez": "[PERSONA_2]", "Elsa Barrientos": "[PERSONA_3]",
    "Aurora Coronado": "[PERSONA_4]", "Luz Mérida": "[PERSONA_5]", "Luis Manuel Alvarado": "[PERSONA_6]",
    "Durán": "[PERSONA_1]", "Vásquez": "[PERSONA_2]", "Barrientos": "[PERSONA_3]",
    "Coronado": "[PERSONA_4]", "Mérida": "[PERSONA_5]", "Alvarado": "[PERSONA_6]",
    "Jean Pierre Venegas": "[ENTREVISTADOR_2]", "Alex Giles": "[PERSONA_7]", "Carlos Ramírez": "[PERSONA_8]",
    "Venegas": "[ENTREVISTADOR_2]", "Giles": "[PERSONA_7]", "Ramírez": "[PERSONA_8]",
}
# los nombres de pila solos se parecen a palabras comunes ("Elena" / "llena"): solo coincidencia casi exacta
REEMPLAZOS_EXACTOS = {
    "Elena": "[PERSONA_1]", "Isabel": "[PERSONA_2]", "Elsa": "[PERSONA_3]", "Aurora": "[PERSONA_4]",
    "Luis": "[PERSONA_6]", "Alex": "[PERSONA_7]", "Carlos": "[PERSONA_8]", "Edgar": "[PERSONA_9]",
    "Jorge": "[ENTREVISTADOR]", "Jean Pierre": "[ENTREVISTADOR_2]", "Ampir": "[ENTREVISTADOR_2]",
}


def seudonimizar_texto(texto, con_nombres=True):
    """Devuelve el texto seudonimizado y cuántas entidades se reemplazaron.

    En los documentos solo hay figuras históricas y autoridades de placas públicas, así que
    ahí se usa con_nombres=False: solo se buscan números que parezcan DNI o teléfono.
    """
    import re
    import voz
    if not isinstance(texto, str) or not texto:
        return "", 0
    reemplazadas = 0
    listas = [(REEMPLAZOS_DIFUSOS, 80), (REEMPLAZOS_EXACTOS, 95)] if con_nombres else []
    for reemplazos, parecido in listas:
        for nombre, seudonimo in reemplazos.items():
            nuevo = voz.seudonimizar(texto, {nombre: seudonimo}, parecido=parecido)
            reemplazadas += nuevo.count(seudonimo) - texto.count(seudonimo)
            texto = nuevo
    texto, n_dni = re.subn(r"\b\d{8}\b", "[DNI]", texto)
    texto, n_telefono = re.subn(r"\b9\d{8}\b", "[TELEFONO]", texto)
    return texto, reemplazadas + n_dni + n_telefono


if __name__ == "__main__":
    tarea = sys.argv[1]
    fuentes = pd.read_csv(RAIZ / "datos" / "fuentes_crudas.csv")
    if tarea in ("ocr", "easyocr"):
        motor = "paddle" if tarea == "ocr" else "easyocr"
        ids = sys.argv[2:] or list(fuentes.loc[fuentes["modalidad"] == "documento", "id"])
        for archivo in sorted(DOCUMENTOS.glob("doc_*.*")):
            if archivo.stem in ids:
                r = ocr(archivo, motor)
                print(f"{r['id']} {motor} {r['segundos']:6.1f} s {len(r['lineas']):3d} líneas", flush=True)
    else:
        modelo = {"asr": "small"}.get(tarea, tarea)
        ids = sys.argv[2:] or list(fuentes.loc[fuentes["modalidad"] == "audio", "id"])
        for fila in fuentes[fuentes["id"].isin(ids)].itertuples():
            r = transcribir(RAIZ / fila.archivo, modelo)
            print(f"{r['id']} {modelo} {r['duracion_seg']:6.1f} s de audio en {r['segundos_proceso']:6.1f} s", flush=True)
