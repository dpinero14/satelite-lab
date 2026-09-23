"""satelite-lab: el satélite cuenta camiones.

Sentinel-2 toma el azul (B02) primero, el verde (B03) 0,527 s después y el rojo (B04)
0,478 s más tarde: 1,005 s entre la primera y la última. Un vehículo que se mueve a
80 km/h recorre 22 m en ese lapso, dos píxeles de 10 m, y aparece en la imagen como
una mancha azul, una verde y una roja corridas en el sentido de marcha. Este repo usa
ese "arcoíris" para contar vehículos en movimiento sobre una ruta, con su sentido y
una velocidad aproximada, en cualquier fecha con cielo despejado desde 2017.

Rutas del repo y constantes. El resto son módulos con funciones puras: `roads` (la
geometría de la ruta), `scenes` (buscar y leer escenas), `detect` (el detector),
`counts` (de detecciones a densidad y series), `figures` (las figuras).
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_PROC = REPO_ROOT / "data" / "processed"
DOCS = REPO_ROOT / "docs"
FIGURES = DOCS / "figures"

# Desfases de toma entre bandas del instrumento MSI, en segundos (Binet et al., citados por el
# dataset europeo de velocidades con Sentinel-2 de 2026): el azul primero, el rojo último.
LAG_B02_B03 = 0.527
LAG_B03_B04 = 0.478
LAG_B02_B04 = LAG_B02_B03 + LAG_B03_B04     # 1,005 s
PIXEL_M = 10.0

# Catálogo STAC abierto de Sentinel-2 L2A en AWS (Element 84), sin cuenta ni clave.
STAC = "https://earth-search.aws.element84.com/v1"
COLLECTION = "sentinel-2-l2a"

# Las rutas del laboratorio, con un punto de referencia sobre cada una y el tramo a recorrer
# desde ese punto, en km a lo largo de la línea del IGN (negativo hacia atrás).
RUTAS = {
    "152": {"nombre": "RN 152, Puelches (La Pampa)", "lon": -65.9, "lat": -38.15, "km": (-60, 10), "que": "la ruta de la arena"},
    "9": {"nombre": "RN 9, Bell Ville (Córdoba)", "lon": -62.7, "lat": -32.6, "km": (-30, 30), "que": "la autopista Rosario-Córdoba"},
    "33": {"nombre": "RN 33, Firmat (Santa Fe)", "lon": -61.5, "lat": -33.45, "km": (-30, 30), "que": "el grano hacia Rosario"},
    "3": {"nombre": "RN 3, Garayalde (Chubut)", "lon": -66.6, "lat": -44.7, "km": (-30, 30), "que": "la Patagonia"},
}

CRS_GEO = "EPSG:4326"

__all__ = ["REPO_ROOT", "DATA_RAW", "DATA_PROC", "DOCS", "FIGURES", "LAG_B02_B03", "LAG_B03_B04", "LAG_B02_B04", "PIXEL_M", "STAC", "COLLECTION", "RUTAS", "CRS_GEO"]
