"""Genera tablas y figuras desde los datos crudos. Ninguna cifra se escribe a mano.

  python -m analysis.make_report
Salida: results/report/ (summary.json, tables.md, fig_*.png)
"""
import csv
import glob
import json
from collections import defaultdict
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from simulation.simulation_config import ROOT

OUT = ROOT / "results" / "report"
ARCHS = ("original", "compact")
LABEL = {"original": "Original 256-256", "compact": "Compacto 64-64"}
FORMATS = ("fp32", "int16", "int8")
# Paleta de referencia dataviz, tres primeras posiciones: validas para todos los pares.
COLOR = {"fp32": "#2a78d6", "int16": "#eb6834", "int8": "#1baf7a", "original": "#2a78d6", "compact": "#eb6834"}
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e6e5e1"


def style():
    plt.rcParams.update({"font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
                         "axes.titlesize": 11, "axes.titlecolor": INK, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True, "legend.frameon": False,
                         "figure.dpi": 150, "savefig.bbox": "tight", "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb"})


def training_curves():
    runs = defaultdict(list)
    for f in glob.glob(str(ROOT / "models/*/seed*/train_log.csv")):
        p = Path(f)
        rows = list(csv.DictReader(open(f, encoding="utf8")))
        if rows:
            runs[p.parts[-3]].append((p.parts[-2], rows))
    return runs


def fig_learning(runs):
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.2), sharex=True)
    for arch in ARCHS:
        for _, rows in runs.get(arch, []):
            s = np.array([float(r["steps"]) for r in rows]) / 1e6
            for ax, key in zip(axes, ("eval_vx", "eval_falls")):
                y = np.array([float(r[key]) for r in rows])
                k = np.ones(5) / 5  # media movil: 5 evaluaciones
                ax.plot(s[2:-2], np.convolve(y, k, "valid"), color=COLOR[arch], lw=1.4, alpha=0.9)
        axes[0].plot([], [], color=COLOR[arch], lw=2, label=LABEL[arch])
    axes[0].set(title="Velocidad en evaluacion (m/s)", xlabel="Pasos de entorno (millones)")
    axes[1].set(title="Caidas por 5 episodios", xlabel="Pasos de entorno (millones)")
    axes[0].axhline(0, color=MUTED, lw=0.6)
    axes[0].legend(loc="lower right")
    fig.savefig(OUT / "fig_aprendizaje.png")
    plt.close(fig)


def results(group):
    out = []
    for f in glob.glob(str(ROOT / "results" / group / "*" / "result.json")):
        out.append(json.loads(Path(f).read_text(encoding="utf8")))
    return out


def by_model(rows, metric):
    table = defaultdict(list)
    for r in rows:
        table[(r["model"], r["precision"])].append((r["seed"], r["summary"][metric]))
    return table


def fig_dots(rows, metric, title, name, unit=""):
    """Un punto por semilla y barra fina en la media: con pocas semillas la dispersion debe verse."""
    t = by_model(rows, metric)
    fig, ax = plt.subplots(figsize=(6.4, 3.1))
    x, ticks = 0, []
    for arch in ARCHS:
        for fmt in FORMATS:
            vals = [v for _, v in t.get((arch, fmt), [])]
            if vals:
                ax.scatter([x] * len(vals), vals, s=34, color=COLOR[fmt], edgecolor="#fcfcfb", linewidth=1, zorder=3)
                ax.plot([x - 0.28, x + 0.28], [np.mean(vals)] * 2, color=INK, lw=1.6, zorder=4)
            ticks.append((x, fmt.upper()))
            x += 1
        x += 0.8
    ax.set_xticks([p for p, _ in ticks], [l for _, l in ticks])
    ax.set_title(title + (f" ({unit})" if unit else ""))
    ax.grid(axis="x", visible=False)
    ax.set_ylim(bottom=0)  # eje desde cero: una diferencia de milesimas no debe parecer grande
    for i, arch in enumerate(ARCHS):
        ax.text(1 + i * 3.8, -0.2, LABEL[arch], ha="center", transform=ax.get_xaxis_transform(), color=MUTED)
    fig.savefig(OUT / name)
    plt.close(fig)


def fig_quant(quant):
    fig, ax = plt.subplots(figsize=(6.4, 3))
    keys = [f"{a}_{f}" for a in ARCHS for f in ("int16", "int8")]
    names = [f"{LABEL[a].split()[0]}\n{f.upper()}" for a in ARCHS for f in ("int16", "int8")]
    for i, k in enumerate(keys):
        vals = [q["models"][k]["mae"] for q in quant if "mae" in q["models"][k]]
        ax.scatter([i] * len(vals), vals, s=34, color=COLOR[k.split("_")[1]], edgecolor="#fcfcfb", zorder=3)
    ax.set_yscale("log")
    ax.set_xticks(range(len(keys)), names)
    ax.set_title("Error absoluto medio de la accion frente a FP32")
    ax.grid(axis="x", visible=False)
    fig.savefig(OUT / "fig_error_cuantizacion.png")
    plt.close(fig)


def fall_rates(rows):
    """Caidas sobre episodios, sumando semillas: {(arquitectura, formato): {fuerza: [caidas, episodios]}}."""
    t = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for r in rows:
        c = t[(r["model"], r["precision"])][r["push"]]
        c[0] += r["summary"]["falls"]
        c[1] += r["summary"]["episodes"]
    return t


def fig_falls(rows):
    t = fall_rates(rows)
    fig, axes = plt.subplots(1, 2, figsize=(8, 3), sharey=True, sharex=True)
    for ax, arch in zip(axes, ARCHS):
        for fmt in FORMATS:
            d = sorted(t[(arch, fmt)].items()) if (arch, fmt) in t else []
            if d:
                ax.plot([f for f, _ in d], [100 * c / n for _, (c, n) in d], color=COLOR[fmt], lw=2, marker="o", ms=5, label=fmt.upper())
        ax.set(title=LABEL[arch], xlabel="Empuje durante 0.1 s (N)")
    axes[0].set(ylabel="Episodios con caida (%)", ylim=(-3, 103))
    fig.legend(*next(a for a in axes if a.lines).get_legend_handles_labels(), loc="upper center", ncols=3, bbox_to_anchor=(0.5, 1.08))
    fig.savefig(OUT / "fig_robustez.png")
    plt.close(fig)


def memory():
    out = {}
    for target in ("esp32", "esp32s3"):
        f = ROOT / "results" / "firmware" / f"size_{target}.json"
        if f.exists():
            out[target] = {x["name"]: x["used"] for x in json.loads(f.read_text(encoding="utf8"))["layout"]}
    return out


def md_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    return "\n".join(lines + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]) + "\n"


def stat(vals, digits=3):
    return f"{np.mean(vals):.{digits}f} +/- {np.std(vals):.{digits}f}" if len(vals) > 1 else f"{vals[0]:.{digits}f}"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    style()
    runs = training_curves()
    fig_learning(runs)
    quant = [json.loads(Path(f).read_text(encoding="utf8")) for f in sorted(glob.glob(str(ROOT / "results/quantization/seed*.json")))]
    b06, b07, b05 = results("B06"), results("B07"), results("B05")
    text = ["# Resultados generados\n", "Tiempos de dispositivo: sin placa no hay mediciones; B05 a B07 usan el ESP32 virtual.\n"]

    rows = []
    for arch in ARCHS:
        for fmt in FORMATS:
            key = f"{arch}_{fmt}"
            qs = [q["models"][key] for q in quant]
            row = [LABEL[arch], fmt.upper(), qs[0]["param_bytes"] if qs else ""]
            for metric in ("mae", "rmse", "p999_abs", "max_abs"):
                v = [q[metric] for q in qs if metric in q]
                row.append(stat(v, 5) if v else "referencia")
            v = [q["outside_calib"] for q in qs if "outside_calib" in q]
            row.append(f"{100 * np.mean(v):.2f}" if v else "")
            rows.append(row)
    text += ["\n## Cuantizacion (observaciones reales de prueba)\n", md_table(["Arquitectura", "Formato", "Parametros (bytes)", "MAE", "RMSE", "Error P99.9", "Error max", "Fuera de calibracion (%)"], rows)]

    pushes = sorted({r["push"] for r in b07})
    groups = [("B06 Locomocion", b06)] + [(f"B07 Empuje de {f:g} N", [r for r in b07 if r["push"] == f]) for f in pushes]
    for title, data in groups:
        rows = []
        for arch in ARCHS:
            for fmt in FORMATS:
                sel = [r for r in data if r["model"] == arch and r["precision"] == fmt]
                if sel:
                    s = [r["summary"] for r in sel]
                    rows.append([LABEL[arch], fmt.upper(), len(s), stat([x["speed_mps"] for x in s]), stat([x["distance_m"] for x in s], 2),
                                 f"{sum(x['falls'] for x in s)} de {sum(x['episodes'] for x in s)}", stat([x["pitch_rms"] for x in s]), stat([x["return"] for x in s], 0)])
        text += [f"\n## {title} (media entre semillas)\n", md_table(["Arquitectura", "Formato", "Semillas", "Velocidad (m/s)", "Distancia (m)", "Caidas", "Pitch RMS (rad)", "Retorno"], rows)]

    mem = memory()
    if mem:
        names = sorted({n for m in mem.values() for n in m})  # el S3 reporta regiones distintas al ESP32
        text += ["\n## B02 Memoria estatica del firmware con los 6 modelos (bytes)\n", md_table(["Objetivo"] + names, [[t] + [m.get(n, "") for n in names] for t, m in mem.items()])]

    if b05:
        rows = []
        for r in sorted(b05, key=lambda r: (ARCHS.index(r["model"]), FORMATS.index(r["precision"]))):
            f = ROOT / "results" / "B05" / r["id"] / "raw.csv"
            d = list(csv.DictReader(open(f, encoding="utf8")))
            host = np.array([float(x["host_us"]) for x in d])
            cyc = np.array([float(x["cycle_us"]) for x in d])
            rows.append([LABEL[r["model"]], r["precision"].upper(), f"{np.median(host):.0f}", f"{np.percentile(host, 99):.0f}", f"{np.median(cyc):.0f}", f"{np.percentile(cyc, 99):.0f}", f"{100 * np.mean(cyc <= 20000):.1f}"])
        text += ["\n## B05 Ciclo HIL con ESP32 virtual\n", "El tiempo del host es real; dispositivo y enlace estan simulados.\n\n",
                 md_table(["Arquitectura", "Formato", "Host mediana (us)", "Host P99 (us)", "Ciclo mediana (us)", "Ciclo P99 (us)", "Ciclos <= 20 ms (%)"], rows)]

    if quant:
        fig_quant(quant)
    if b06:
        fig_dots(b06, "speed_mps", "Velocidad con politica cuantizada", "fig_velocidad.png", "m/s")
    if b07:
        fig_falls(b07)
    (OUT / "tables.md").write_text("".join(text), encoding="utf8")
    print("".join(text))


if __name__ == "__main__":
    main()
