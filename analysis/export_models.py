"""Exporta los 6 modelos (2 arquitecturas x FP32, INT16, INT8) a C y mide el error contra FP32.

  python -m analysis.export_models --seed 0
Salidas: firmware/inference/models_generated.c, models/<arch>/quant_seed<n>.npz, results/quantization/seed<n>.json
"""
import argparse
import json

import numpy as np

from reinforcement_learning.evaluation import quantization as qz
from simulation.simulation_config import ROOT

ARCHS = {"original": 256, "compact": 64}
FORMATS = ("fp32", "int16", "int8")
PERCENTILES = (100.0, 99.99, 99.9)


def model_id(arch, fmt):
    return list(ARCHS).index(arch) * 3 + FORMATS.index(fmt)


def load_actor(arch, seed, checkpoint="best.pt"):
    import torch  # solo aqui: la exportacion a C y las pruebas no necesitan torch
    state = torch.load(ROOT / "models" / arch / f"seed{seed}" / checkpoint, map_location="cpu")
    return qz.actor_layers(state["actor"])


def random_actor(hidden, seed=0):
    """Solo para medir tamanos de firmware antes de terminar el entrenamiento."""
    r = np.random.default_rng(seed)
    dims = [(hidden, 36), (hidden, hidden), (12, hidden)]
    return [(r.normal(0, 1 / np.sqrt(i), (o, i)).astype(np.float32), r.normal(0, 0.05, o).astype(np.float32)) for o, i in dims]


def best_quantization(layers, calib, fmt):
    """Elige el recorte de calibracion con menor error sobre una particion de validacion interna."""
    cut = int(len(calib) * 0.8)
    fit, val = calib[:cut], calib[cut:]
    ref = qz.forward_fp32(layers, val)
    scored = [(qz.action_errors(ref, qz.forward_quant(qz.quantize(layers, fit, fmt, pc), val))["mae"], pc) for pc in PERCENTILES]
    pc = min(scored)[1]
    return qz.quantize(layers, calib, fmt, pc), pc


def _array(ctype, name, values, per_line=16):
    flat = np.asarray(values).ravel()
    if ctype == "float":
        items = [f"{np.float32(v).item():.9g}f" if np.isfinite(v) else "0.0f" for v in flat]
        items = [s if ("." in s or "e" in s) else s.replace("f", ".0f") for s in items]
    elif ctype == "int64_t":
        items = [f"{int(v)}LL" for v in flat]
    else:
        items = [str(int(v)) for v in flat]
    rows = [", ".join(items[i:i + per_line]) for i in range(0, len(items), per_line)]
    return f"static const {ctype} {name}[{len(items)}] = {{\n" + ",\n".join(rows) + "\n};\n"


def emit_model(arch, fmt, layers, q):
    p = f"{arch}_{fmt}"
    src, entries = [], []
    if q is None:
        for i, (w, b) in enumerate(layers):
            src += [_array("float", f"{p}_w{i}", w), _array("float", f"{p}_b{i}", b)]
            entries.append(f"{{{w.shape[1]}, {w.shape[0]}, {p}_w{i}, {p}_b{i}, NULL, NULL, NULL}}")
        extra, qmax, fmt_c = "NULL", 0, "POLICY_F32"
    else:
        wtype = "int8_t" if fmt == "int8" else "int16_t"
        src.append(_array("float", f"{p}_inv", (1.0 / q["input_scale"]).astype(np.float32)))
        for i, ly in enumerate(q["layers"]):
            src += [_array(wtype, f"{p}_w{i}", ly["w"]), _array("int64_t", f"{p}_b{i}", ly["b"])]
            if "mult" in ly:
                src += [_array("int32_t", f"{p}_m{i}", ly["mult"]), _array("uint8_t", f"{p}_s{i}", ly["shift"])]
                tail = f"{p}_m{i}, {p}_s{i}, NULL"
            else:
                src.append(_array("float", f"{p}_o{i}", ly["out_scale"]))
                tail = f"NULL, NULL, {p}_o{i}"
            entries.append(f"{{{ly['w'].shape[1]}, {ly['w'].shape[0]}, {p}_w{i}, {p}_b{i}, {tail}}}")
        extra, qmax, fmt_c = f"{p}_inv", q["qmax"], "POLICY_I8" if fmt == "int8" else "POLICY_I16"
    body = ", ".join(entries)
    src.append(f'static const policy_model_t {p} = {{"{p}", {model_id(arch, fmt)}, {fmt_c}, {qmax}, {extra}, {{{body}}}}};\n')
    return "".join(src), p


def export(seed, allow_random=False):
    out_dir = ROOT / "results" / "quantization"
    out_dir.mkdir(parents=True, exist_ok=True)
    parts, names, report = [], [], {"seed": seed, "models": {}}
    for arch, hidden in ARCHS.items():
        data = ROOT / "datasets" / f"{arch}_seed{seed}.npz"
        trained = data.exists() and (ROOT / "models" / arch / f"seed{seed}" / "best.pt").exists()
        if not trained and not allow_random:
            raise FileNotFoundError(f"falta {arch} seed{seed}; usar --allow-random solo para medir tamanos")
        if trained:
            layers = load_actor(arch, seed)
            d = np.load(data)
            calib, test = d["calib"], d["test"]
        else:
            layers = random_actor(hidden)
            r = np.random.default_rng(1)
            calib, test = r.normal(0, 1, (2000, 36)).astype(np.float32), r.normal(0, 1, (2000, 36)).astype(np.float32)
        ref = qz.forward_fp32(layers, test)
        saved = {}
        for fmt in FORMATS:
            entry = {"model_id": model_id(arch, fmt), "trained": trained}
            if fmt == "fp32":
                q = None
                entry["param_bytes"] = qz.model_bytes(layers)
            else:
                q, pc = best_quantization(layers, calib, fmt)
                out = qz.forward_quant(q, test)
                worst = np.abs(ref - out).max(axis=1)  # la cola viene de muestras fuera del rango calibrado, que saturan
                outside = ((test < calib.min(0)) | (test > calib.max(0))).any(axis=1)
                entry.update(calibration_percentile=pc, param_bytes=qz.model_bytes(layers, q), **qz.action_errors(ref, out),
                             p999_abs=float(np.percentile(worst, 99.9)), outside_calib=float(outside.mean()))
                saved[fmt] = q
            src, name = emit_model(arch, fmt, layers, q)
            parts.append(src)
            names.append(name)
            report["models"][f"{arch}_{fmt}"] = entry
        np.savez_compressed(ROOT / "models" / arch / f"quant_seed{seed}.npz", q=np.array(saved, dtype=object),
                            layers=np.array(layers, dtype=object))
    table = ", ".join(f"&{n}" for n in names)
    code = ("// Generado por analysis/export_models.py. No editar.\n#include <stddef.h>\n#include \"policy.h\"\n\n" + "".join(parts)
            + f"\nconst policy_model_t *const policy_models[] = {{{table}}};\nconst int policy_model_count = {len(names)};\n")
    (ROOT / "firmware" / "inference" / "models_generated.c").write_text(code, encoding="utf8", newline="\n")
    (out_dir / f"seed{seed}.json").write_text(json.dumps(report, indent=1), encoding="utf8")
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--allow-random", action="store_true")
    a = ap.parse_args()
    print(json.dumps(export(a.seed, a.allow_random), indent=1))
