"""Observaciones reales del simulador para calibrar y validar cuantizacion, y para el modo A del benchmark.

Calibracion y prueba salen de semillas disjuntas. Parte de los episodios lleva ruido de accion para cubrir estados
fuera de la trayectoria nominal, que es donde una politica cuantizada se aleja de la original.
"""
import argparse

import numpy as np

from analysis.export_models import load_actor
from reinforcement_learning.evaluation.quantization import forward_fp32
from simulation.observations import ObservationStats
from simulation.pybullet_env import BipedEnv
from simulation.simulation_config import ROOT, load_config

RESET_NOISE = 0.02


def rollouts(layers, episodes, seed, action_noise=0.05):
    env = BipedEnv(max_steps=load_config()["episode"]["eval_steps"])
    env.seed(seed)
    rng = np.random.default_rng(seed)
    obs_all = []
    for ep in range(episodes):
        obs = env.reset(RESET_NOISE)
        std = action_noise if ep % 2 else 0.0
        while True:
            obs_all.append(obs)
            a = forward_fp32(layers, obs) + rng.normal(0, std, 12) if std else forward_fp32(layers, obs)
            obs, _, term, trunc, _ = env.step(a)
            if term or trunc:
                break
    env.close()
    return np.array(obs_all, np.float32)


def collect(arch, seed, episodes=40):
    layers = load_actor(arch, seed)
    calib = rollouts(layers, episodes, 1000 + seed)
    test = rollouts(layers, episodes, 2000 + seed)
    stats = ObservationStats()
    for o in test:
        stats.update(o)
    out = ROOT / "datasets" / f"{arch}_seed{seed}.npz"
    out.parent.mkdir(exist_ok=True)
    np.savez_compressed(out, calib=calib, test=test)
    print(arch, seed, "calib", calib.shape, "test", test.shape)
    return out, stats.summary()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--arch", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--episodes", type=int, default=40)
    a = ap.parse_args()
    collect(a.arch, a.seed, a.episodes)
