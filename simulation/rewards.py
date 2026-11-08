"""Recompensa del articulo (ecuaciones 32, 33 y 37) con el curriculum de tres fases.

Cambio declarado: el articulo penaliza ||a||^2, que con control por torque es el torque normalizado.
Con control por posicion a es una referencia, asi que se usa (tau/tau_max)^2 promedio del periodo de control.
"""
import numpy as np


def phase_weights(total_steps, cfg):
    """Pesos y numero de fase para un total de pasos de entorno. La fase 2 sube w_vel con rampa lineal."""
    r = cfg["reward"]
    lo, hi = r["phase_bounds"]
    if total_steps < lo:
        return dict(r["phases"][0]), 1
    if total_steps < hi:
        w = dict(r["phases"][1])
        w["w_vel"] *= (total_steps - lo) / (hi - lo)
        return w, 2
    return dict(r["phases"][2]), 3


def compute_reward(w, v_x, z, roll, pitch, energy, fallen, cfg):
    r = cfg["reward"]
    h = cfg["robot"]["spawn_height"]
    v = float(np.clip(v_x, -r["vel_clip"], r["vel_clip"]))
    h_rel = float(np.clip((z - r["height_floor"]) / (h - r["height_floor"]), 0.0, 1.0))
    return (w["w_vel"] * v * (1.0 if v >= 0 else r["backward_gain"]) + w["w_height"] * h_rel + w["w_alive"]
            - w["w_energy"] * energy - w["w_roll"] * abs(roll) - w["w_pitch"] * abs(pitch) - w["w_fall"] * float(fallen))
