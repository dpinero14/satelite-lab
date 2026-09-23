"""Las figuras: la ruta enderezada con sus detecciones, el arcoíris de un vehículo, y las series.

Misma paleta que el resto de la serie: fondo oscuro, tinta clara, ámbar para lo que importa.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

BG, INK, MUTED, RULE = "#0e1b25", "#f2f2f2", "#8fa3b0", "#22333f"
ACENTO, CONTEXTO, AZUL, VERDE, ROJO = "#f2b134", "#6b8799", "#3b8ed0", "#4caf50", "#e05a4e"


def _style(ax):
    ax.set_facecolor(BG)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)


def rgb_image(s: dict, p_lo: float = 2.0, p_hi: float = 99.7) -> np.ndarray:
    """La franja como imagen RGB (a lo largo en x, a lo ancho en y), estirada por percentiles."""
    rgb = np.nan_to_num(np.stack([s["red"], s["green"], s["blue"]], -1))
    v = rgb[rgb > 0]
    lo, hi = (np.percentile(v, [p_lo, p_hi]) if v.size else (0, 1))
    img = np.clip((rgb - lo) / max(hi - lo, 1.0), 0, 1)
    return np.transpose(img, (1, 0, 2))


def anomaly_image(z: dict, escala: float = 6.0, signo: int = 1) -> np.ndarray:
    """La anomalía de cada banda como color (rojo = B04, verde = B03, azul = B02): un móvil se ve como arcoíris."""
    zz = np.stack([z["red"], z["green"], z["blue"]], -1) * signo
    return np.transpose(np.clip(zz / escala, 0, 1), (1, 0, 2))


def strip_figure(s: dict, z: dict, det: pd.DataFrame, path: str | Path, titulo: str, subtitulo: str, km0: float = 0.0, ventana_km: tuple[float, float] | None = None) -> Path:
    """Dos paneles apilados: la ruta enderezada en color real y su anomalía por banda, con las detecciones marcadas."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    img, an = rgb_image(s), anomaly_image(z)
    n = img.shape[1]
    k0, k1 = (0, n) if ventana_km is None else (int(ventana_km[0] * 100), int(ventana_km[1] * 100))
    fig, axes = plt.subplots(2, 1, figsize=(14, 4.6), dpi=170)
    fig.patch.set_facecolor(BG)
    fig.subplots_adjust(left=0.03, right=0.99, top=0.80, bottom=0.12, hspace=0.35)
    for ax, im, nombre in zip(axes, (img, an), ("color real", "anomalía por banda: azul B02, verde B03, rojo B04")):
        _style(ax)
        ax.imshow(im[:, k0:k1], aspect="auto", interpolation="nearest", extent=(km0 + k0 / 100, km0 + k1 / 100, im.shape[0], 0))
        ax.set_yticks([])
        ax.set_title(nombre, color=MUTED, fontsize=9, loc="left", pad=3)
        for _, o in det.iterrows():
            if k0 <= o["k"] < k1:
                x = km0 + o["k"] / 100
                ax.add_patch(Rectangle((x - 0.03, o["a"] - 1.5), 0.06 + abs(o["lag"]) / 100, 3, fill=False, edgecolor=ACENTO if o["sentido"] > 0 else AZUL, linewidth=1.2))
    axes[1].set_xlabel("km a lo largo del tramo", color=MUTED, fontsize=9)
    fig.text(0.03, 0.93, titulo, color=INK, fontsize=15, fontweight="bold")
    fig.text(0.03, 0.875, subtitulo, color=MUTED, fontsize=9.5)
    fig.text(0.03, 0.02, "satelite-lab · Sentinel-2 L2A (Copernicus, vía AWS) · eje de ruta del IGN · ámbar: a favor del eje, azul: en contra", color=MUTED, fontsize=8)
    fig.savefig(path, facecolor=BG)
    plt.close(fig)
    return Path(path)


def rainbow_figure(s: dict, z: dict, o: pd.Series, path: str | Path, titulo: str, half: int = 8, zoom_note: str = "") -> Path:
    """Un vehículo de cerca: el recorte en color real, la anomalía por banda y los tres perfiles a lo largo."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    k, a = int(o["k"]), int(o["a"])
    k0, k1 = max(0, k - half), min(z["blue"].shape[0], k + half + 1)
    img, an = rgb_image(s)[:, k0:k1], anomaly_image(z)[:, k0:k1]
    fig = plt.figure(figsize=(11, 4.2), dpi=170)
    fig.patch.set_facecolor(BG)
    gs = fig.add_gridspec(2, 2, width_ratios=[1.1, 1.4], left=0.05, right=0.98, top=0.80, bottom=0.14, hspace=0.45, wspace=0.18)
    ax1, ax2, ax3 = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[:, 1])
    for ax, im, nombre in ((ax1, img, "color real"), (ax2, an, "anomalía por banda")):
        _style(ax)
        ax.imshow(im, aspect="equal", interpolation="nearest")
        ax.set_xticks([]); ax.set_yticks([])
        ax.set_title(nombre, color=MUTED, fontsize=9, loc="left", pad=3)
    _style(ax3)
    ax3.grid(axis="y", color=RULE, linewidth=0.8, zorder=0)
    xs = (np.arange(k0, k1) - k) * 10
    for banda, color, etiqueta in (("blue", AZUL, "B02 azul (primero)"), ("green", VERDE, "B03 verde (+0,53 s)"), ("red", ROJO, "B04 rojo (+1,005 s)")):
        ax3.plot(xs, z[banda][k0:k1, a] * o["signo"], color=color, linewidth=2, marker="o", markersize=3.5, label=etiqueta, zorder=3)
    ax3.axvline(0, color=RULE, linewidth=1)
    ax3.set_xlabel("metros a lo largo de la ruta desde la mancha azul", color=MUTED, fontsize=9)
    ax3.set_ylabel("anomalía (MAD)", color=MUTED, fontsize=9)
    ax3.legend(frameon=False, labelcolor=INK, fontsize=8.5, loc="upper right")
    fig.text(0.05, 0.93, titulo, color=INK, fontsize=14, fontweight="bold")
    fig.text(0.05, 0.87, f"corrimiento azul→rojo de {abs(int(o['lag']))} píxeles en 1,005 s ≈ {int(o['velocidad_kmh'])} km/h, "
             f"{'a favor' if o['sentido'] > 0 else 'en contra'} del eje; {'claro' if o['signo'] > 0 else 'oscuro'} sobre el fondo. {zoom_note}", color=MUTED, fontsize=9.5)
    fig.savefig(path, facecolor=BG)
    plt.close(fig)
    return Path(path)


def series_figure(por_periodo: pd.DataFrame, path: str | Path, titulo: str, subtitulo: str, referencia: dict | None = None, ylabel: str = "vehículos en movimiento por 100 km, por pasada") -> Path:
    """Densidad por período con su error de conteo, y la partición por sentido debajo."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    g = por_periodo
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 6), dpi=170, sharex=True, gridspec_kw={"height_ratios": [2.2, 1]})
    fig.patch.set_facecolor(BG)
    fig.subplots_adjust(left=0.08, right=0.98, top=0.82, bottom=0.10, hspace=0.12)
    for ax in (a1, a2):
        _style(ax)
        ax.grid(axis="y", color=RULE, linewidth=0.8, zorder=0)
    x = g.index
    a1.fill_between(x, g["por_100km"] - g["error_100km"], g["por_100km"] + g["error_100km"], color=ACENTO, alpha=0.18, zorder=2)
    a1.plot(x, g["por_100km"], color=ACENTO, linewidth=2.4, marker="o", markersize=4, zorder=3)
    for xi, v, p in zip(x, g["por_100km"], g["pasadas"]):
        a1.text(xi, v + g["error_100km"].max() * 0.15, f"{p} pasadas", ha="center", va="bottom", color=MUTED, fontsize=7.5)
    if referencia:
        for etiqueta, (xi, v) in referencia.items():
            a1.plot([xi], [v], marker="D", color=CONTEXTO, markersize=6, zorder=4)
            a1.text(xi, v, "  " + etiqueta, color=CONTEXTO, fontsize=8, va="center")
    a1.set_ylabel(ylabel, color=MUTED, fontsize=9)
    a1.set_ylim(bottom=0)
    a2.bar(x, g["pct_pos"], width=200, color=ACENTO, zorder=3, alpha=0.9)
    a2.bar(x, 100 - g["pct_pos"], bottom=g["pct_pos"], width=200, color=AZUL, zorder=3, alpha=0.9)
    a2.set_ylim(0, 100)
    a2.set_ylabel("% por sentido", color=MUTED, fontsize=9)
    fig.text(0.08, 0.93, titulo, color=INK, fontsize=15, fontweight="bold")
    fig.text(0.08, 0.875, subtitulo, color=MUTED, fontsize=9.5)
    fig.text(0.08, 0.02, "satelite-lab · Sentinel-2 · días hábiles con menos de 5 % de nubes · banda: error de conteo (raíz de N)", color=MUTED, fontsize=8)
    fig.savefig(path, facecolor=BG)
    plt.close(fig)
    return Path(path)


def routes_figure(tabla: pd.DataFrame, path: str | Path, titulo: str, subtitulo: str) -> Path:
    """Barras por ruta: densidad medida por el satélite contra el TMDA de Vialidad 2016, en dos escalas."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 4.8), dpi=170)
    fig.patch.set_facecolor(BG)
    fig.subplots_adjust(left=0.08, right=0.92, top=0.80, bottom=0.16)
    _style(ax)
    ax.grid(axis="y", color=RULE, linewidth=0.8, zorder=0)
    x = np.arange(len(tabla))
    ax.bar(x - 0.2, tabla["por_100km"], width=0.38, color=ACENTO, zorder=3, label="satélite: vehículos en movimiento por 100 km")
    ax.errorbar(x - 0.2, tabla["por_100km"], yerr=tabla["error_100km"], fmt="none", ecolor=INK, elinewidth=1, capsize=3, zorder=4)
    ax.set_ylabel("por 100 km, por pasada", color=ACENTO, fontsize=9)
    ax2 = ax.twinx()
    _style(ax2)
    ax2.bar(x + 0.2, tabla["tmda"], width=0.38, color=CONTEXTO, zorder=3, label="Vialidad: TMDA 2016, vehículos por día")
    ax2.set_ylabel("TMDA 2016, vehículos por día", color=CONTEXTO, fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(tabla["nombre"], color=INK, fontsize=9)
    h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, frameon=False, labelcolor=INK, fontsize=8.5, loc="upper center", bbox_to_anchor=(0.5, 1.02), ncol=2)
    ax.set_ylim(0, max(tabla["por_100km"] + tabla["error_100km"]) * 1.25)
    ax2.set_ylim(0, tabla["tmda"].max() * 1.25)
    fig.text(0.08, 0.92, titulo, color=INK, fontsize=15, fontweight="bold")
    fig.text(0.08, 0.865, subtitulo, color=MUTED, fontsize=9.5)
    fig.text(0.08, 0.03, "satelite-lab · Sentinel-2 · Vialidad Nacional (IDE Transporte) · el TMDA cuenta todos los vehículos, el satélite solo los que se mueven y contrastan", color=MUTED, fontsize=8)
    fig.savefig(path, facecolor=BG)
    plt.close(fig)
    return Path(path)


def sand_figure(anual: pd.DataFrame, arena_mt: dict[int, float], path: str | Path, titulo: str, subtitulo: str) -> Path:
    """El índice del satélite (barras) contra la arena bombeada por año en Vaca Muerta (línea), en dos escalas."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 4.8), dpi=170)
    fig.patch.set_facecolor(BG)
    fig.subplots_adjust(left=0.08, right=0.91, top=0.80, bottom=0.14)
    _style(ax)
    ax.grid(axis="y", color=RULE, linewidth=0.8, zorder=0)
    x = anual.index.to_numpy()
    ax.bar(x, anual["por_100km"], color=ACENTO, width=0.6, zorder=3, label="satélite: vehículos en movimiento por 100 km, RN 152")
    ax.errorbar(x, anual["por_100km"], yerr=anual["error_100km"], fmt="none", ecolor=INK, elinewidth=1, capsize=3, zorder=4)
    ax.set_ylabel("por 100 km, por pasada", color=ACENTO, fontsize=9)
    ax.set_ylim(0, (anual["por_100km"] + anual["error_100km"]).max() * 1.3)
    ax2 = ax.twinx()
    _style(ax2)
    anios = sorted(a for a in arena_mt if a >= x.min() and a <= x.max())
    ax2.plot(anios, [arena_mt[a] for a in anios], color=CONTEXTO, linewidth=2.2, marker="s", markersize=5, zorder=5, label="registro de fractura: arena bombeada, millones de t")
    ax2.set_ylabel("arena bombeada en Vaca Muerta, millones de t por año", color=CONTEXTO, fontsize=9)
    ax2.set_ylim(0, max(arena_mt[a] for a in anios) * 1.3)
    ax.set_xticks(x)
    ax.set_xticklabels([str(v) for v in x], color=MUTED, fontsize=9)
    h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, frameon=False, labelcolor=INK, fontsize=8.5, loc="upper center", bbox_to_anchor=(0.5, 1.02), ncol=2)
    fig.text(0.08, 0.92, titulo, color=INK, fontsize=15, fontweight="bold")
    fig.text(0.08, 0.865, subtitulo, color=MUTED, fontsize=9.5)
    fig.text(0.08, 0.03, "satelite-lab · Sentinel-2 · Secretaría de Energía, registro de fractura (Adjunto IV), cuenca Neuquina no convencional, nacional más importada", color=MUTED, fontsize=8)
    fig.savefig(path, facecolor=BG)
    plt.close(fig)
    return Path(path)


__all__ = ["BG", "INK", "MUTED", "RULE", "ACENTO", "rgb_image", "anomaly_image", "strip_figure", "rainbow_figure", "series_figure", "routes_figure", "sand_figure"]
