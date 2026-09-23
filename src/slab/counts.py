"""De detecciones a números: densidad por 100 km, por sentido, y series por fecha.

Una pasada del satélite es una foto: lo que se cuenta es cuántos vehículos en movimiento
hay sobre un tramo en ese instante (a media mañana, hora local). Para pasar de esa densidad
a vehículos por día hace falta una velocidad y un perfil horario; acá se usa una velocidad
media y se declara el supuesto. Lo robusto es comparar densidades entre rutas y entre fechas
con el mismo método, no el número absoluto por día.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def density(det: pd.DataFrame, km: float) -> dict:
    """Resumen de una pasada sobre un tramo: cuántos, por sentido, claros u oscuros, y por clase de velocidad."""
    n = len(det)
    return {"km": km, "n": n, "por_100km": 100.0 * n / km if km > 0 else np.nan,
            "n_pos": int((det["sentido"] > 0).sum()) if n else 0, "n_neg": int((det["sentido"] < 0).sum()) if n else 0,
            "n_claros": int((det["signo"] > 0).sum()) if n else 0, "n_oscuros": int((det["signo"] < 0).sum()) if n else 0,
            "n_lag2": int((det["lag"].abs() == 2).sum()) if n else 0, "n_lag3": int((det["lag"].abs() >= 3).sum()) if n else 0,
            "n_alta": int((det["confianza"] == "alta").sum()) if n and "confianza" in det else 0,
            "amp_b_mediana": float(det["amp_b"].abs().median()) if n else np.nan}


def daily_from_density(veh_per_100km: float, velocidad_kmh: float = 80.0, horas_equivalentes: float = 24.0) -> float:
    """Vehículos por día que implica una densidad instantánea, si circularan a `velocidad_kmh` y el flujo del instante fuera el de todo el día.

    flujo (veh/h) = densidad (veh/km) x velocidad (km/h); por día = flujo x horas equivalentes.
    Es una cota gruesa: el flujo de media mañana suele estar por encima del promedio del día.
    """
    return veh_per_100km / 100.0 * velocidad_kmh * horas_equivalentes


def series(rows: list[dict]) -> pd.DataFrame:
    """Tabla por escena a partir de los resúmenes de `density`, con fecha y escena."""
    df = pd.DataFrame(rows)
    if len(df) == 0:
        return df
    df["fecha"] = pd.to_datetime(df["fecha"])
    return df.sort_values("fecha").reset_index(drop=True)


def by_period(df: pd.DataFrame, freq: str = "YS", min_km: float = 20.0) -> pd.DataFrame:
    """Densidad media por período (año por defecto) sumando detecciones y kilómetros válidos de todas las pasadas."""
    d = df[df["km"] >= min_km].copy()
    g = d.groupby(pd.Grouper(key="fecha", freq=freq)).agg(pasadas=("n", "size"), n=("n", "sum"), km=("km", "sum"), n_pos=("n_pos", "sum"), n_neg=("n_neg", "sum"),
                                                          n_lag2=("n_lag2", "sum"), n_lag3=("n_lag3", "sum"), n_alta=("n_alta", "sum"))
    g["alta_100km"] = 100.0 * g["n_alta"] / g["km"]
    g = g[g["pasadas"] > 0]
    g["por_100km"] = 100.0 * g["n"] / g["km"]
    # error estándar de una tasa de conteo: raíz del total sobre los km
    g["error_100km"] = 100.0 * np.sqrt(g["n"].clip(lower=1)) / g["km"]
    g["pct_pos"] = 100.0 * g["n_pos"] / g["n"].where(g["n"] > 0)
    return g


__all__ = ["density", "daily_from_density", "series", "by_period"]
