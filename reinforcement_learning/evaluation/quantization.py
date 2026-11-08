"""Cuantizacion del actor 36-H-H-12 y referencia numerica exacta del firmware.

Formato (igual para INT8 e INT16, documentation/formato_cuantizacion.md):
- Pesos: simetricos por canal de salida, zero-point 0.
- Activaciones: simetricas por tensor; tras ReLU solo usan la mitad positiva, zero-point 0.
- Entrada: escala por variable (H20). s_in[i] se pliega en W1, asi el microcontrolador solo multiplica por 1/s_in[i].
- Sesgos: enteros a escala s_w[o] * s_x.
- Reescalado entero: y = (acc * mult[o] + redondeo) >> shift[o]. Sin flotantes entre capas.
- Salida: mu = acc * out_scale[o] en float, luego tanh. Son 12 operaciones.

Esta aritmetica es la que ejecuta firmware/inference/policy.c; las pruebas exigen igualdad bit a bit.
"""
import numpy as np

QMAX = {"int8": 127, "int16": 32767}
MULT_BITS = 24  # acc de INT16 llega a 2^39: acc * mult debe caber en int64


def actor_layers(state_dict):
    """Solo la rama determinista: red comun y mu. log_std no se despliega."""
    get = lambda k: state_dict[k].detach().cpu().numpy().astype(np.float32)
    return [(get("net.0.weight"), get("net.0.bias")), (get("net.2.weight"), get("net.2.bias")),
            (get("mu.weight"), get("mu.bias"))]


def forward_fp32(layers, obs):
    """Referencia en float32. Acepta una observacion o un lote."""
    x = np.asarray(obs, np.float32)
    for i, (w, b) in enumerate(layers):
        x = x @ w.T + b
        if i < len(layers) - 1:
            x = np.maximum(x, 0)
    return np.tanh(x)


def _multiplier(real):
    """Representa real > 0 como mult * 2^-shift con mult de MULT_BITS bits."""
    real = np.asarray(real, np.float64)
    if np.any(real <= 0):
        raise ValueError("escala no positiva")
    mant, exp = np.frexp(real)  # mant en [0.5, 1)
    mult = np.round(mant * (1 << MULT_BITS)).astype(np.int64)
    shift = (MULT_BITS - exp).astype(np.int64)
    if np.any(shift < 1) or np.any(shift > 62):
        raise ValueError("reescalado fuera de rango")
    return mult, shift


def quantize(layers, calib_obs, fmt, percentile=100.0):
    """Calibra con observaciones reales del simulador. percentile < 100 recorta valores extremos."""
    qmax = QMAX[fmt]
    calib = np.asarray(calib_obs, np.float32)
    in_range = np.maximum(np.percentile(np.abs(calib), percentile, axis=0), 1e-3)
    s_in = (in_range / qmax).astype(np.float64)

    acts, x = [], calib
    for i, (w, b) in enumerate(layers[:-1]):
        x = np.maximum(x @ w.T + b, 0)
        acts.append(max(float(np.percentile(x, percentile)), 1e-6) / qmax)

    q = {"format": fmt, "qmax": qmax, "input_scale": s_in, "layers": []}
    s_x = None
    for i, (w, b) in enumerate(layers):
        w = w.astype(np.float64)
        # Primera capa: escala de entrada plegada, la entrada entera ya vale x / s_in[i].
        w_eff = w * s_in[None, :] if i == 0 else w * s_x
        s_w = np.maximum(np.abs(w_eff).max(axis=1), 1e-12) / qmax
        wq = np.clip(np.round(w_eff / s_w[:, None]), -qmax, qmax).astype(np.int32)
        bq = np.round(b.astype(np.float64) / s_w).astype(np.int64)
        layer = {"w": wq, "b": bq}
        if i < len(layers) - 1:
            layer["mult"], layer["shift"] = _multiplier(s_w / acts[i])
            s_x = acts[i]
        else:
            layer["out_scale"] = s_w.astype(np.float32)
        q["layers"].append(layer)
    return q


def quantize_input(obs, q):
    x = np.asarray(obs, np.float32) * (1.0 / q["input_scale"]).astype(np.float32)
    return np.clip(np.rint(x), -q["qmax"], q["qmax"]).astype(np.int64)


def forward_quant(q, obs):
    """Misma aritmetica entera que policy.c. Acepta una observacion o un lote."""
    x = quantize_input(obs, q)
    for layer in q["layers"][:-1]:
        acc = x @ layer["w"].T.astype(np.int64) + layer["b"]
        rounding = np.int64(1) << (layer["shift"] - 1)
        x = np.clip((acc * layer["mult"] + rounding) >> layer["shift"], 0, q["qmax"])
    last = q["layers"][-1]
    acc = x @ last["w"].T.astype(np.int64) + last["b"]
    return np.tanh(acc.astype(np.float32) * last["out_scale"]).astype(np.float32)


def action_errors(reference, test):
    d = np.asarray(reference, np.float64) - np.asarray(test, np.float64)
    return {"mae": float(np.abs(d).mean()), "rmse": float(np.sqrt((d * d).mean())), "max_abs": float(np.abs(d).max())}


def model_bytes(layers, q=None):
    """Bytes de parametros en flash, sin contar codigo."""
    if q is None:
        return sum(w.size * 4 + b.size * 4 for w, b in layers)
    wbytes = 1 if q["format"] == "int8" else 2
    total = q["input_scale"].size * 4
    for i, ly in enumerate(q["layers"]):
        total += ly["w"].size * wbytes + ly["b"].size * 8
        total += ly["w"].shape[0] * (4 if i == len(q["layers"]) - 1 else 5)
    return total
