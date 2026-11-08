"""Vector de 36 observaciones con las convenciones de RBIPEDO (curriculum_env.py).

Indices: 0-11 q, 12-23 qd, 24 altura, 25-27 roll/pitch/yaw, 28-30 v lineal mundo, 31-33 v angular mundo,
34-35 fuerza normal pie izquierdo y derecho.
"""
import numpy as np

OBS_DIM = 36
NAMES = ([f"q{i}" for i in range(12)] + [f"qd{i}" for i in range(12)] + ["z_norm", "roll", "pitch", "yaw"]
         + ["vx", "vy", "vz", "wx", "wy", "wz", "f_left", "f_right"])


def build_observation(raw, cfg):
    o, h = cfg["observation"], cfg["robot"]["spawn_height"]
    obs = np.concatenate([
        np.clip(raw["q"], -o["joint_pos_clip"], o["joint_pos_clip"]),
        np.clip(raw["qd"], -o["joint_vel_clip"], o["joint_vel_clip"]),
        [(raw["pos"][2] - h) / h],
        raw["euler"],
        np.clip(raw["lin_vel"], -o["lin_vel_clip"], o["lin_vel_clip"]),
        np.clip(raw["ang_vel"], -o["ang_vel_clip"], o["ang_vel_clip"]),
        np.clip(np.asarray(raw["foot_forces"]) / o["force_scale"], 0.0, 1.0),
    ]).astype(np.float32)
    if obs.shape != (OBS_DIM,):
        raise ValueError(f"observacion de tamano {obs.shape}")
    if not np.all(np.isfinite(obs)):
        raise FloatingPointError(f"observacion no finita en {[NAMES[i] for i in np.flatnonzero(~np.isfinite(obs))]}")
    return obs


class ObservationStats:
    """Minimo, maximo, media y desviacion por variable (Welford)."""

    def __init__(self):
        self.n, self.mean, self.m2 = 0, np.zeros(OBS_DIM), np.zeros(OBS_DIM)
        self.min, self.max = np.full(OBS_DIM, np.inf), np.full(OBS_DIM, -np.inf)

    def update(self, obs):
        self.n += 1
        d = obs - self.mean
        self.mean += d / self.n
        self.m2 += d * (obs - self.mean)
        self.min, self.max = np.minimum(self.min, obs), np.maximum(self.max, obs)

    def summary(self):
        std = np.sqrt(self.m2 / max(self.n - 1, 1))
        return {n: {"min": float(a), "max": float(b), "mean": float(m), "std": float(s)}
                for n, a, b, m, s in zip(NAMES, self.min, self.max, self.mean, std)}
