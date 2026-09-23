import numpy as np
import pandas as pd

from slab.detect import VELOCIDAD, detect, lag_of, running_median
from slab.counts import by_period, daily_from_density, density, series


def _strip(n=400, m=9, seed=0):
    """Franja sintética: fondo distinto por banda con ruido, eje válido, sin objetos."""
    rng = np.random.default_rng(seed)
    s = {"blue": 500 + rng.normal(0, 15, (n, m)), "green": 650 + rng.normal(0, 18, (n, m)), "red": 800 + rng.normal(0, 20, (n, m)),
         "valid": np.ones((n, m), bool), "along": np.arange(n) * 10.0, "x": np.arange(n) * 10.0, "y": np.zeros(n)}
    return s


def _put(s, k, a, lag, amp=300.0):
    """Un vehículo claro que avanza `lag` muestras entre el azul y el rojo (el verde en el medio)."""
    s["blue"][k, a] += amp
    s["green"][k + int(round(lag * 0.52)), a] += amp
    s["red"][k + lag, a] += amp


def test_velocidades_de_cada_corrimiento():
    assert VELOCIDAD[2] == 72 and VELOCIDAD[3] == 107      # 20 y 30 m en 1,005 s


def test_mediana_movil_ignora_nan():
    a = np.array([[1.0], [np.nan], [3.0], [100.0], [5.0]])
    out = running_median(a, win=1)
    assert out[1, 0] == 2.0 and out[3, 0] == 5.0


def test_lag_of_encuentra_el_corrimiento():
    p = np.zeros(13); p[6] = 5.0; p[5] = 2.0
    q = np.roll(p, 2)
    assert lag_of(p, q)[0] == 2
    assert lag_of(p, np.roll(p, -3))[0] == -3
    assert lag_of(p, p)[0] == 0


def test_detecta_moviles_con_sentido_y_no_los_fijos():
    s = _strip()
    _put(s, 60, 4, 2)                 # a favor, 72 km/h
    _put(s, 160, 4, -3)               # en contra, 107 km/h
    for k in ("blue", "green", "red"):
        s[k][260, 4] += 400.0         # objeto fijo: anómalo en las tres bandas en el mismo lugar
    det = detect(s)
    assert len(det) == 2
    d = det.set_index("k")
    assert d.loc[60, "lag"] == 2 and d.loc[60, "sentido"] == 1 and d.loc[60, "velocidad_kmh"] == 72
    assert d.loc[160, "lag"] == -3 and d.loc[160, "sentido"] == -1 and d.loc[160, "velocidad_kmh"] == 107
    assert (det["signo"] == 1).all() and (det["confianza"] == "alta").all()


def test_objeto_oscuro_y_borde_invalido():
    s = _strip()
    _put(s, 100, 4, 2, amp=-250.0)    # vehículo oscuro sobre fondo claro
    s["valid"][200:, :] = False       # media franja fuera de la escena
    _put(s, 300, 4, 2)                # no debe contarse: está en la parte inválida
    det = detect(s)
    assert len(det) == 1 and det.loc[0, "signo"] == -1 and det.loc[0, "k"] == 100


def test_densidad_y_dia():
    det = detect(_strip()) if False else pd.DataFrame({"sentido": [1, -1, 1], "signo": [1, 1, -1], "lag": [2, 3, 2], "amp_b": [0.5, 0.4, -0.3], "confianza": ["alta", "media", "alta"]})
    d = density(det, km=50.0)
    assert d["n"] == 3 and d["por_100km"] == 6.0 and d["n_pos"] == 2 and d["n_lag3"] == 1 and d["n_alta"] == 2
    assert abs(daily_from_density(6.0, 80.0) - 115.2) < 1e-9     # 0,06 veh/km x 80 km/h x 24 h
    rows = [dict(fecha="2025-03-04", **density(det, 50.0)), dict(fecha="2025-03-09", **density(det.iloc[:1], 40.0)), dict(fecha="2026-01-10", **density(det, 10.0))]
    g = by_period(series(rows), "YS")
    assert list(g.index.year) == [2025] and g.iloc[0]["pasadas"] == 2 and abs(g.iloc[0]["por_100km"] - 100 * 4 / 90) < 1e-9
