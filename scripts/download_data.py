"""Baja lo que el laboratorio necesita en disco: la geometría de las rutas (IGN) y los conteos de Vialidad para comparar.

Las imágenes Sentinel-2 no se bajan: se leen por ventana desde el catálogo abierto de AWS
cada vez que hacen falta. Corre con `python scripts/download_data.py`.
"""

import sys
from pathlib import Path

import certifi
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from slab import DATA_RAW, RUTAS  # noqa: E402
from slab.roads import fetch_routes  # noqa: E402

# TMDA 2016 de Vialidad Nacional por tramo, con la descripción de cada tramo, vía la IDE de Transporte.
# El servidor no manda sus eslabones intermedios (Let's Encrypt YR2 y la ISRG Root YR firmada en cruz por
# ISRG Root X1, que sí está en certifi); se agregan al paquete de certifi. No se agrega ninguna raíz nueva.
IDE_WFS = "https://ide.transporte.gob.ar/geoserver/observ/ows"
CAPA_TMDA = "observ:_3.4.1.4.1.tmda_2016_view"
CERTS = Path(__file__).resolve().parent / "certs"


def ca_bundle(path: Path = DATA_RAW / "ca_bundle.pem") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    extras = "\n".join(p.read_text(encoding="utf-8").strip() for p in sorted(CERTS.glob("*.pem")))
    path.write_text(Path(certifi.where()).read_text(encoding="utf-8").strip() + "\n" + extras + "\n", encoding="utf-8")
    return path


def bajar_tmda(destino: Path = DATA_RAW / "tmda_2016.geojson", timeout: int = 600) -> None:
    if destino.exists() and destino.stat().st_size > 0:
        print(f"  ya está: {destino.name}")
        return
    r = requests.get(IDE_WFS, params={"service": "WFS", "version": "1.0.0", "request": "GetFeature", "typeName": CAPA_TMDA, "maxFeatures": 5000,
                                      "outputFormat": "application/json"},
                     timeout=timeout, verify=str(ca_bundle()), headers={"User-Agent": "satelite-lab/0.1 (+https://github.com/dpinero14)"})
    r.raise_for_status()
    destino.write_bytes(r.content)
    print(f"  {destino.name}: {len(r.content) / 1e6:.1f} MB")


def main() -> None:
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    print("rutas del IGN:")
    g = fetch_routes(tuple(RUTAS))
    print(f"  {len(g)} tramos de {g['rtn'].nunique()} rutas")
    print("TMDA 2016 de Vialidad:")
    bajar_tmda()
    print("listo")


if __name__ == "__main__":
    main()
