"""El detector: vehículos en movimiento como corrimiento entre bandas a lo largo de la ruta enderezada.

Para cada banda, el fondo es la mediana móvil a lo largo de la ruta, carril por carril, y la
anomalía es la diferencia en unidades de dispersión robusta (MAD). Donde el azul es anómalo
se toman los perfiles de anomalía de las tres bandas a lo largo y se busca el corrimiento
(en muestras de 10 m) que mejor alinea el rojo con el azul. Corrimiento cero: un objeto fijo
(un techo, un cartel). Corrimiento de dos o tres: algo que avanzó 20 o 30 m en 1,005 s, entre
54 y 125 km/h. El verde tiene que caer entre los dos. El signo del corrimiento da el sentido,
porque el azul se toma primero.

Es una versión propia del principio de Fisser et al. (2022, *Detecting Moving Trucks on Roads
Using Sentinel-2 Data*): ellos clasifican píxeles con un bosque aleatorio entrenado a mano;
acá se usa la geometría de la ruta y una regla explícita, sin entrenamiento.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from . import LAG_B02_B04, PIXEL_M

# velocidad implícita en cada corrimiento entero (10 m por muestra en 1,005 s)
VELOCIDAD = {lag: round(lag * PIXEL_M / LAG_B02_B04 * 3.6) for lag in (1, 2, 3, 4)}


def running_median(a: np.ndarray, win: int = 30) -> np.ndarray:
    """Mediana móvil a lo largo del eje 0 (ventana ±win muestras), por columna, ignorando NaN."""
    n = a.shape[0]
    out = np.full_like(a, np.nan, dtype=np.float64)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)     # ventanas enteras de NaN fuera de la escena
        for i in range(n):
            out[i] = np.nanmedian(a[max(0, i - win): i + win + 1], axis=0)
    return out


def anomalies(s: dict, win: int = 30) -> tuple[dict, dict]:
    """Anomalía por banda: `z` en unidades de MAD y `amp` relativa al fondo. NaN fuera de la franja válida → 0."""
    z, amp = {}, {}
    for k in ("blue", "green", "red"):
        v = np.where(s["valid"], s[k], np.nan)
        bg = running_median(v, win)
        mad = 1.4826 * running_median(np.abs(v - bg), win) + 1.0
        z[k] = np.nan_to_num((v - bg) / mad)
        amp[k] = np.nan_to_num((v - bg) / (bg + 1.0))
    return z, amp


def lag_of(p_ref: np.ndarray, p: np.ndarray, max_lag: int = 3, half: int = 3) -> tuple[int, float]:
    """Corrimiento de `p` respecto de `p_ref` que maximiza la correlación de una ventana de ±half muestras alrededor del centro."""
    n = len(p_ref)
    c = n // 2
    a = p_ref[c - half: c + half + 1]
    best = (0, -1.0)
    for lag in range(-max_lag, max_lag + 1):
        b = p[c - half + lag: c + half + 1 + lag]
        if len(b) != len(a):
            continue
        den = np.linalg.norm(a) * np.linalg.norm(b)
        corr = float(a @ b / den) if den > 0 else -1.0
        if corr > best[1]:
            best = (lag, corr)
    return best


def detect(s: dict, z_thr: float = 3.0, corr_min: float = 0.5, min_lag: int = 2, max_lag: int = 3, half_win: int = 6, border: int = 1, win: int = 30,
           z_r_min: float = 2.0, z_g_min: float = 1.5, suma_min: float = 9.0) -> pd.DataFrame:
    """Vehículos en movimiento en la franja `s`. Una fila por objeto.

    Un objeto exige: azul anómalo (|z| > z_thr), rojo alineado con un corrimiento de `min_lag` a `max_lag`
    muestras (correlación > corr_min) y anómalo ahí (> z_r_min), verde entre los dos (> z_g_min), y una
    suma de anomalías sobre la trayectoria (azul + verde + rojo) mayor que `suma_min` y mayor que la
    suma en el mismo lugar, que es lo que daría un objeto fijo.

    Columnas: k (muestra a lo largo), a (carril), lag (corrimiento azul→rojo en muestras, con signo),
    lag_g, corr, signo (1 claro, -1 oscuro), sentido (+1 a favor de la línea, -1 en contra), confianza (alta o media),
    velocidad_kmh, z_b, z_g, z_r, amp_b, amp_r, score, along_m, x, y.
    """
    z, amp = anomalies(s, win)
    zb, zg, zr = z["blue"], z["green"], z["red"]
    n, m = zb.shape
    ok = s["valid"].copy()
    for dk in range(-half_win, half_win + 1):
        ok &= np.roll(s["valid"], dk, axis=0)
    ok[:half_win] = False
    ok[n - half_win:] = False
    ok[:, :border] = False
    ok[:, m - border:] = False
    seed = ok & (np.abs(zb) > z_thr)
    objs = []
    for (k, a) in np.argwhere(seed):
        sign = float(np.sign(zb[k, a]))
        a0, a1 = max(0, a - 1), min(m, a + 2)
        pb = (zb[k - half_win: k + half_win + 1, a0:a1] * sign).sum(1)
        pg = (zg[k - half_win: k + half_win + 1, a0:a1] * sign).sum(1)
        pr = (zr[k - half_win: k + half_win + 1, a0:a1] * sign).sum(1)
        lag_r, c_r = lag_of(pb, pr, max_lag)
        lag_g, c_g = lag_of(pb, pg, max_lag)
        if c_r < corr_min or abs(lag_r) < min_lag:
            continue
        if not (min(0, lag_r) <= lag_g <= max(0, lag_r)):
            continue
        zr_corrido = float((zr[k + lag_r, a0:a1] * sign).max())
        zg_corrido = float((zg[k + lag_g, a0:a1] * sign).max())
        if zr_corrido < z_r_min or zg_corrido < z_g_min:
            continue
        suma_movil = abs(zb[k, a]) + zg_corrido + zr_corrido
        suma_fija = abs(zb[k, a]) + float((zg[k, a0:a1] * sign).max()) + float((zr[k, a0:a1] * sign).max())
        if suma_movil < suma_min or suma_movil <= suma_fija:
            continue
        # confianza alta: firma fuerte y bien alineada; media: cumple las reglas pero con poco margen
        confianza = "alta" if (suma_movil >= 12.0 and c_r >= 0.75) else "media"
        objs.append({"k": int(k), "a": int(a), "lag": int(lag_r), "lag_g": int(lag_g), "corr": c_r, "signo": int(sign), "sentido": int(np.sign(lag_r)), "confianza": confianza,
                     "velocidad_kmh": VELOCIDAD[abs(lag_r)], "z_b": float(zb[k, a]), "z_g": zg_corrido, "z_r": zr_corrido,
                     "amp_b": float(amp["blue"][k, a]), "amp_r": float(amp["red"][k + lag_r, a]), "score": float(abs(zb[k, a]) * c_r),
                     "along_m": float(s["along"][k]), "x": float(s["x"][k]), "y": float(s["y"][k])})
    cols = ["k", "a", "lag", "lag_g", "corr", "signo", "sentido", "confianza", "velocidad_kmh", "z_b", "z_g", "z_r", "amp_b", "amp_r", "score", "along_m", "x", "y"]
    if not objs:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(objs).sort_values("score", ascending=False)
    # dos semillas vecinas son el mismo vehículo: queda la de mejor puntaje
    keep = []
    for _, o in df.iterrows():
        if all(abs(o["k"] - p["k"]) > 3 or abs(o["a"] - p["a"]) > 2 for p in keep):
            keep.append(o)
    return pd.DataFrame(keep, columns=cols).reset_index(drop=True)


__all__ = ["VELOCIDAD", "running_median", "anomalies", "lag_of", "detect"]
