"""Benchmark B01 a B07. Con --port usa hardware; sin el, ESP32 virtual, y los resultados quedan marcados como tales.

  python -m host.experiment_runner --group B01 --seed 0
  python -m host.experiment_runner --group B05 --seed 0 --port COM7 --platform esp32
"""
import argparse
import json

import numpy as np

from analysis.export_models import ARCHS, FORMATS, model_id
from host.data_logger import ExperimentLog, deadline_stats, latency_stats
from host.hil_controller import run_episode, wait_ready
from host.serial_interface import DeviceLink, DeviceTimeout, open_serial
from host.virtual_esp32 import VirtualESP32
from reinforcement_learning.evaluation.quantization import action_errors, forward_fp32, forward_quant
from simulation.pybullet_env import BipedEnv
from simulation.simulation_config import ROOT, load_config

RESET_NOISE = 0.02
TIMEOUT_S = 0.015
# B01 y B04 miden latencia: una espera corta descartaria justo las inferencias lentas. El plazo de 20 ms se evalua aparte.
ISOLATED_TIMEOUT_S = 0.5


def load_models(seed):
    out = {}
    for arch in ARCHS:
        d = np.load(ROOT / "models" / arch / f"quant_seed{seed}.npz", allow_pickle=True)
        q, layers = d["q"].item(), [tuple(x) for x in d["layers"]]
        out[model_id(arch, "fp32")] = ("fp32", layers)
        for fmt in ("int16", "int8"):
            out[model_id(arch, fmt)] = ("quant", q[fmt])
    return out


def connect(a, models):
    if a.port:
        return DeviceLink(open_serial(a.port, a.baud), reopen=lambda: open_serial(a.port, a.baud), timeout_s=TIMEOUT_S)
    return DeviceLink(VirtualESP32(models, infer_us=a.virtual_infer_us, simulate_wire=True), timeout_s=TIMEOUT_S)


def matrix(archs):
    return [(arch, fmt, model_id(arch, fmt)) for arch in archs for fmt in FORMATS]


def isolated(a, link, models):
    """Modo A, B01 y B04: observaciones almacenadas, sin PyBullet en la ruta critica."""
    link.timeout_s = ISOLATED_TIMEOUT_S
    for arch, fmt, mid in matrix(a.archs):
        obs = np.load(ROOT / "datasets" / f"{arch}_seed{a.seed}.npz")["test"]
        idx = np.random.default_rng(a.seed).integers(0, len(obs), a.samples)
        log = ExperimentLog(a.group, ["i", "infer_us", "round_trip_us", "free_heap", "timeout"], model=arch, precision=fmt,
                            platform=a.platform, seed=a.seed, repetitions=a.samples, mode="A")
        infer, rtt, missed, ref, got = [], [], [], [], []
        kind, m = models[model_id(arch, "fp32")]
        for i, k in enumerate(idx):
            try:
                r = link.infer(obs[k], mid)
                infer.append(r["infer_us"])
                rtt.append(r["round_trip_us"])
                missed.append(False)
                ref.append(forward_fp32(m, obs[k]))
                got.append(r["actions"])
                log.row(i, r["infer_us"], round(r["round_trip_us"], 1), r["free_heap"], 0)
            except DeviceTimeout:
                rtt.append(ISOLATED_TIMEOUT_S * 1e6)
                missed.append(True)
                log.row(i, "", "", "", 1)
        summary = {"infer_us": latency_stats(infer), "round_trip_us": latency_stats(rtt),
                   "deadline": deadline_stats(rtt, missed=missed), "action_error": action_errors(ref, got) if ref else None,
                   "link": {"timeouts": link.stats.timeouts, "crc_errors": link.crc_errors, "stale": link.stats.stale}}
        print(arch, fmt, log.close(summary).name, json.dumps(summary["infer_us"]))


def closed_loop(a, link, models, push=None):
    """Modo B, B05, B06 y B07. Misma lista de semillas para todos los modelos: comparacion pareada."""
    cfg = load_config()
    env = BipedEnv(max_steps=cfg["episode"]["eval_steps"] if not a.long else 3000)
    cols = ["episode", "cycle", "infer_us", "transfer_us", "host_us", "cycle_us", "missed", "x", "z", "pitch", "roll"]
    for arch, fmt, mid in matrix(a.archs):
        log = ExperimentLog(a.group, cols, model=arch, precision=fmt, platform=a.platform, seed=a.seed, repetitions=a.episodes, mode="B",
                            push=push)
        results = []
        for ep in range(a.episodes):
            env.seed(a.seed * 100_000 + ep)
            pu = None
            if push:
                sign = 1 if ep % 2 else -1
                pu = (100, [0, sign * push, 0] if ep % 4 > 1 else [sign * push, 0, 0], 0.1)
            r = run_episode(env, link, mid, RESET_NOISE, pu)
            for i, c in enumerate(r["cycles"]):
                log.row(ep, i, c["infer_us"], round(c["transfer_us"], 1), round(c["host_us"], 1), round(c["cycle_us"], 1), int(c["missed"]),
                        round(c["x"], 4), round(c["z"], 4), round(c["pitch"], 4), round(c["roll"], 4))
            del r["cycles"]
            results.append(r)
        s = {k: float(np.mean([r[k] for r in results])) for k in ("return", "duration_s", "distance_m", "speed_mps", "pitch_rms", "roll_rms", "peak_force_n")}
        s["falls"] = int(sum(r["fallen"] for r in results))
        s["episodes"] = len(results)
        s["speed_std"] = float(np.std([r["speed_mps"] for r in results]))
        print(arch, fmt, log.close(s).name, json.dumps(s))
    env.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", required=True, choices=["B01", "B04", "B05", "B06", "B07"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--port")
    ap.add_argument("--archs", nargs="+", default=list(ARCHS), choices=list(ARCHS))
    ap.add_argument("--baud", type=int, default=921600)
    ap.add_argument("--platform", default="virtual", help="esp32 o esp32s3; virtual si no hay placa")
    ap.add_argument("--samples", type=int, default=1000)
    ap.add_argument("--episodes", type=int, default=20)
    ap.add_argument("--long", action="store_true", help="episodios de 60 s")
    ap.add_argument("--virtual-infer-us", type=int, default=500)
    ap.add_argument("--push-n", type=float, default=60.0)
    args = ap.parse_args()
    if args.port and args.platform == "virtual":
        ap.error("con --port hay que declarar --platform")
    mods = load_models(args.seed)
    dev = connect(args, mods)
    if args.port:
        print(wait_ready(dev))
    if args.group in ("B01", "B04"):
        isolated(args, dev, mods)
    else:
        closed_loop(args, dev, mods, args.push_n if args.group == "B07" else None)
