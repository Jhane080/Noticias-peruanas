"""Descarga el corpus de la Tarea 2 desde Wikimedia Commons y OpenSLR 73.

    .venv\\Scripts\\python.exe descargar.py

Todo lo que baja tiene licencia libre (dominio público, CC0, CC BY o CC BY-SA) y su
atribución queda en datos/fuentes_crudas.csv. Los archivos van a datos/raw/, que no se
sube a GitHub: este script es la forma de recuperarlos.

Reglas de cortesía con los servidores: User-Agent que dice quién pide y una pausa de
1,5 segundos entre descargas.
"""
import io
import math
import random
import time
import urllib.parse
import urllib.request
import zipfile
import json
from pathlib import Path

import pandas as pd

CARPETA = Path(__file__).resolve().parent / "datos"
DOCUMENTOS = CARPETA / "raw" / "documentos"
AUDIO = CARPETA / "raw" / "audio"
UA = {"User-Agent": "tarea2-diplomado-pucp/2026 (https://github.com/Jhane080/Noticias-peruanas)"}
PAUSA = 1.5
API = "https://commons.wikimedia.org/w/api.php"

# Documentos: (id, tipo, archivo en Commons, página si es PDF)
DOCS = [
    # impresos nítidos: libros y folletos peruanos del siglo XIX y XX, escaneados
    ("doc_001", "impreso", "Constitución Política del Perú (1856).pdf", 5),
    ("doc_002", "impreso", "Constitución política del Perú reformada por el Congreso de 1860.pdf", 6),
    ("doc_003", "impreso", "Guia de la Exposicion industrial de Lima 28 de julio de 1869 - con detalles interesantes, pormenores curiosos, lista alfabetica de los exponentes etc. etc (IA guiadelaexposici00expo).pdf", 9),
    ("doc_004", "impreso", "Historia de la fundación de Lima (IA aja4162.0001.001.umich.edu).pdf", 15),
    ("doc_005", "impreso", "Apéndice a Mis últimas tradiciones peruanas (1910).pdf", 17),
    ("doc_006", "impreso", "Boletín de la Sociedad Geográfica de Lima. (IA boletndelasocied1019soci).pdf", 21),
    ("doc_007", "impreso", "Pisco-punch-mercurio-peruano-1791.jpg", None),
    ("doc_008", "impreso", "Historia de los límites del Perú (Historiadeloslim00angu).pdf", 13),
    # fotos de celular: placas en la calle y una revista fotografiada sobre una mesa
    ("doc_009", "foto", "Placa del Palacio de Justicia de Lima.jpg", None),
    ("doc_010", "foto", "Placa del ex-Círculo Militar del Perú en Lima.jpg", None),
    ("doc_011", "foto", "Casa de José Santos Chocano en Lima - Placa (der.) 01.jpg", None),
    ("doc_012", "foto", "Placa de Mariano Nechochea en el Saga Falabella de Miraflores (Lima, Perú) (detalle).jpg", None),
    ("doc_013", "foto", "Placa por el centenario de la inmolación de los mártires de Chicago en el Rímac 01.jpg", None),
    ("doc_014", "foto", "LimaPlacaCatedral1985.JPG", None),
    ("doc_015", "foto", "Revista jurisprudencia institucional reniec (6780228236).jpg", None),
    ("doc_016", "foto", "Placa Juan Luis Rospigliosi y Gomez Sanchez, Barranco.jpg", None),
    # manuscritos: documentos coloniales y del siglo XIX escritos a mano
    ("doc_017", "manuscrito", "Relación de antigüedades deste reino del Pirú (1613).jpg", None),
    ("doc_018", "manuscrito", "Manuscrito de Perú (F. Gil de Lemos).Texto.jpg", None),
    ("doc_019", "manuscrito", "Manuscrito de Perú (F. Gil de Lemos).Portada.jpg", None),
    ("doc_020", "manuscrito", "Manuscrito de Perú (F. Gil de Lemos).Índice.jpg", None),
    ("doc_021", "manuscrito", "Capitulacón de Ayacucho2.jpg", None),
    ("doc_022", "manuscrito", "Nuevacoronica.jpg", None),
    ("doc_023", "manuscrito", "Diego Dávila 1856 \"Provincia de Yauyos\".jpg", None),
    ("doc_024", "manuscrito", "Bajo y Tamboril para baylar cantando. Tonada del Chimo.jpg", None),
    ("doc_025", "manuscrito", "Acllacuna.jpg", None),
    # reemplazos por si alguno se descarta en la limpieza (ilegible o no es un documento)
    ("doc_026", "foto", "Casa de José Santos Chocano en Lima - Placa (izq.).jpg", None),
    ("doc_027", "foto", "Pasaje José Olaya en el distrito de Lima 04.jpg", None),
    ("doc_028", "manuscrito", "Manuscrito de Perú (F. Gil de Lemos).Tabla.jpg", None),
    # segunda tanda de reemplazos: con los criterios de limpieza quedaron 7 fotos y 7 manuscritos válidos
    ("doc_029", "foto", "Casa de José Santos Chocano en Lima - Placa (der.) 02.jpg", None),
    ("doc_030", "foto", "Commemorative plaque to Ioannes Paulus II in the Cathedral of Lima.jpg", None),
    ("doc_031", "foto", "José Olaya, plaza San Martín.jpg", None),
    ("doc_032", "manuscrito", "GuamanPomadeAyala-MuertedeAtagualpaInca.jpg", None),
    ("doc_033", "manuscrito", "Bogotá POMA1005v.jpg", None),
    ("doc_034", "manuscrito", "Guaman Poma - Fraile mercedario Morua.jpg", None),
    ("doc_035", "manuscrito", "Cofradía de Nuestra Señora de la Soledad en la Villa de Pisco.jpg", None),
]

# Audios de Commons en español hablado en el Perú: (nombre local, archivo en Commons)
AUDIOS_COMMONS = [
    ("agustino_1.ogg", "Entrevista 1 en la Av. Rivagüero - El Agustino.ogg"),
    ("agustino_2.ogg", "Entrevista 2 en la Av. Rivagüero - El Agustino.ogg"),
    ("fenmucarinap_1.ogg", "Entrevista-Aurora Coronado-organización de mujeres indígenas-fiestas patrias.ogg"),
    ("fenmucarinap_2.ogg", "Entrevista a Luz Merida-Organización de mujeres indígenas-fiestas patrias-protesta.ogg"),
    ("plaza_huancayo.ogg", "Entrevista a un ciudadano venezolano al respecto de fiestas patrias en la Plaza Constitución de la Ciudad de Huancayo.ogg"),
    ("medio_tiempo.opus", "Entrevista en el medio tiempo.opus"),
    ("entrevista_1.wav", "Entrevista 1,.wav"),
    ("entrevista_2.wav", "Entrevista 2.wav"),
    ("entrevista_3.wav", "Entrevista 3.wav"),
    ("entrevista_4.wav", "Entrevista 4.wav"),
    # quechua de Huaylas: solo para la bonificación con MMS
    ("shansha_quechua.ogg", "Elena Figueroa - Entrevista sobre Españolada, Shansha, Áncash, Perú.ogg"),
]

OPENSLR73 = "https://www.openslr.org/resources/73/es_pe_{sexo}.zip"


def pedir(url, rango=None):
    cabecera = dict(UA)
    if rango:
        cabecera["Range"] = f"bytes={rango[0]}-{rango[1]}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=cabecera), timeout=180) as r:
        return r.read()


def info_commons(titulo, pagina=None):
    """URL de descarga, licencia, autor y descripción de un archivo de Commons."""
    parametros = {"action": "query", "format": "json", "titles": "File:" + titulo, "prop": "imageinfo",
                  "iiprop": "url|size|extmetadata"}
    if pagina:
        # para un PDF, Commons entrega la página pedida ya convertida en imagen (solo en anchos estándar)
        parametros["iiurlwidth"] = 1280
        parametros["iiurlparam"] = f"page{pagina}-1280px"
    respuesta = json.loads(pedir(API + "?" + urllib.parse.urlencode(parametros)))
    pagina_api = next(iter(respuesta["query"]["pages"].values()))
    if "imageinfo" not in pagina_api:
        raise FileNotFoundError(titulo)
    ii = pagina_api["imageinfo"][0]
    meta = ii.get("extmetadata", {})

    def campo(nombre):
        texto = meta.get(nombre, {}).get("value", "")
        return " ".join(urllib.parse.unquote(texto).replace("<", " <").split())[:300]

    # el enlace por número de página (curid) evita publicar nombres de personas que traen algunos títulos
    url_descarga = ii["url"]
    if pagina:
        # la API siempre devuelve la página a 500 px; pedimos la misma miniatura a 1280 px para que el OCR lea mejor
        url_descarga = ii["thumburl"].split("?")[0].replace("-500px-", "-1280px-")
    return {
        "url_descarga": url_descarga,
        "fuente_url": f"https://commons.wikimedia.org/?curid={pagina_api['pageid']}",
        "licencia": campo("LicenseShortName"),
        "autor": campo("Artist"),
        "descripcion": campo("ImageDescription"),
        "duracion_commons": ii.get("duration"),
    }


def bajar_documentos():
    DOCUMENTOS.mkdir(parents=True, exist_ok=True)
    filas = []
    for id_doc, tipo, titulo, pagina in DOCS:
        info = info_commons(titulo, pagina)
        extension = ".jpg" if pagina else Path(titulo).suffix.lower().replace(".jpeg", ".jpg")
        ruta = DOCUMENTOS / f"{id_doc}{extension}"
        if not ruta.exists():
            ruta.write_bytes(pedir(info["url_descarga"]))
            time.sleep(PAUSA)
        filas.append({"id": id_doc, "modalidad": "documento", "tipo": tipo, "archivo": ruta.relative_to(CARPETA.parent).as_posix(),
                      "titulo_commons": titulo, "pagina_pdf": pagina, **info})
        print(f"{id_doc} {tipo:10} {info['licencia']:15} {titulo[:60]}")
    return pd.DataFrame(filas)


def bajar_audios_commons():
    AUDIO.mkdir(parents=True, exist_ok=True)
    filas = []
    for local, titulo in AUDIOS_COMMONS:
        info = info_commons(titulo)
        ruta = AUDIO / local
        if not ruta.exists():
            ruta.write_bytes(pedir(info["url_descarga"]))
            time.sleep(PAUSA)
        filas.append({"id": Path(local).stem, "modalidad": "audio", "archivo": ruta.relative_to(CARPETA.parent).as_posix(),
                      "titulo_commons": titulo, **info})
        print(f"{local:25} {info['licencia']:15} {info['duracion_commons']} s")
    return pd.DataFrame(filas)


class ZipRemoto(io.RawIOBase):
    """El zip de OpenSLR pesa 900 MB: lo leemos por partes (HTTP Range) y solo bajamos las frases que usamos.

    Copiado de datos.py de la Sesión 13.
    """

    BLOQUE = 1 << 20

    def __init__(self, url):
        self.url, self.pos, self.buf_ini, self.buf = url, 0, 0, b""
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA, method="HEAD"), timeout=60) as r:
            self.size = int(r.headers["Content-Length"])

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = {0: offset, 1: self.pos + offset, 2: self.size + offset}[whence]
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        n = min(n, self.size - self.pos)
        if n <= 0:
            return b""
        fin = self.pos + n
        if not (self.buf_ini <= self.pos and fin <= self.buf_ini + len(self.buf)):
            self.buf_ini = self.pos
            self.buf = pedir(self.url, (self.pos, min(self.pos + max(n, self.BLOQUE), self.size) - 1))
        datos = self.buf[self.pos - self.buf_ini:fin - self.buf_ini]
        self.pos += len(datos)
        return datos


def guardar_16k(contenido, ruta):
    import soundfile as sf
    from scipy.signal import resample_poly
    x, sr = sf.read(io.BytesIO(contenido), dtype="float32")
    if x.ndim > 1:
        x = x.mean(axis=1)
    if sr != 16_000:
        g = math.gcd(sr, 16_000)
        x = resample_poly(x, 16_000 // g, sr // g).astype("float32")
    sf.write(ruta, x, 16_000)


def bajar_openslr73(n_por_sexo=6, frases_por_clip=4, semilla=7):
    """Clips de español peruano leído (OpenSLR 73, CC BY-SA 4.0), con su transcripción oficial.

    Cada clip une varias frases seguidas de un mismo hablante para que dure unos 20 segundos.
    Además arma una entrevista simulada con frases de una mujer y un hombre alternadas, que
    sirve para probar la diarización porque sabemos quién habla en cada tramo.
    """
    import numpy as np
    import soundfile as sf
    AUDIO.mkdir(parents=True, exist_ok=True)
    filas, turnos = [], {}
    rng = random.Random(semilla)
    for sexo in ["female", "male"]:
        z = zipfile.ZipFile(ZipRemoto(OPENSLR73.format(sexo=sexo)))
        lineas = z.read("line_index.tsv").decode("utf-8").strip().splitlines()
        tabla = pd.DataFrame([l.split("\t") for l in lineas], columns=["id", "texto"])
        tabla["hablante"] = tabla["id"].str.rsplit("_", n=1).str[0]
        tabla = tabla[tabla["texto"].str.split().str.len().between(6, 20)]
        hablantes = sorted(tabla["hablante"].unique())
        rng.shuffle(hablantes)
        for i, hablante in enumerate(hablantes[:n_por_sexo + 1]):
            frases = tabla[tabla["hablante"] == hablante].head(frases_por_clip)
            partes = []
            for _, frase in frases.iterrows():
                tmp = AUDIO / "tmp.wav"
                guardar_16k(z.read(f"{frase['id']}.wav"), tmp)
                x, _ = sf.read(tmp, dtype="float32")
                partes.append(x)
            tmp.unlink()
            textos = [t.strip() for t in frases["texto"]]
            if i == n_por_sexo:  # el último hablante de cada sexo va a la entrevista simulada
                turnos[sexo] = list(zip(partes, textos))
                continue
            clip_id = f"openslr_{'m' if sexo == 'female' else 'h'}{i + 1:02d}"
            silencio = np.zeros(int(0.5 * 16_000), dtype="float32")
            audio = np.concatenate([p for x in partes for p in (x, silencio)])
            sf.write(AUDIO / f"{clip_id}.wav", audio, 16_000)
            filas.append({"id": clip_id, "modalidad": "audio", "archivo": f"datos/raw/audio/{clip_id}.wav",
                          "titulo_commons": None, "fuente_url": "https://www.openslr.org/73/",
                          "licencia": "CC BY-SA 4.0", "autor": "Google (Guevara-Rukoz et al., 2020)",
                          "descripcion": f"Español peruano leído, {len(textos)} frases de un hablante ({hablante})",
                          "transcripcion_oficial": " ".join(textos)})
        time.sleep(PAUSA)
    # entrevista simulada: turnos alternados mujer / hombre con pausas de 0,7 s
    silencio = np.zeros(int(0.7 * 16_000), dtype="float32")
    audio, textos = [], []
    for (xm, tm), (xh, th) in zip(turnos["female"], turnos["male"]):
        audio += [xm, silencio, xh, silencio]
        textos += [f"[HABLANTE_1] {tm}", f"[HABLANTE_2] {th}"]
    sf.write(AUDIO / "entrevista_simulada.wav", np.concatenate(audio), 16_000)
    filas.append({"id": "entrevista_simulada", "modalidad": "audio", "archivo": "datos/raw/audio/entrevista_simulada.wav",
                  "titulo_commons": None, "fuente_url": "https://www.openslr.org/73/", "licencia": "CC BY-SA 4.0",
                  "autor": "Google (Guevara-Rukoz et al., 2020)",
                  "descripcion": "Entrevista simulada: frases reales de una mujer y un hombre peruanos, alternadas",
                  "transcripcion_oficial": " ".join(textos)})
    return pd.DataFrame(filas)


if __name__ == "__main__":
    import sys
    partes = sys.argv[1:] or ["documentos", "audio", "openslr"]
    tablas = []
    if "documentos" in partes:
        tablas.append(bajar_documentos())
    if "audio" in partes:
        tablas.append(bajar_audios_commons())
    if "openslr" in partes:
        tablas.append(bajar_openslr73())
    nueva = pd.concat(tablas, ignore_index=True)
    destino = CARPETA / "fuentes_crudas.csv"
    if destino.exists():
        vieja = pd.read_csv(destino, dtype=str)
        nueva = pd.concat([vieja[~vieja["id"].isin(nueva["id"])], nueva.astype(str)], ignore_index=True)
    nueva.to_csv(destino, index=False)
    print(f"\n{len(nueva)} archivos registrados en {destino}")
