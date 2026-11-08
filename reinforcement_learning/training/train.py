"""Entrenamiento SAC con workers paralelos de PyBullet.

  python -m reinforcement_learning.training.train --arch compact --seed 0 --steps 3000000
"""
import argparse
import csv
import json
import multiprocessing as mp
import platform
import random
import time
from pathlib import Path

import numpy as np
import pybullet as p
import torch

from reinforcement_learning.training.sac import SAC, Replay
from simulation.pybullet_env import BipedEnv
from simulation.rewards import phase_weights
from simulation.simulation_config import ROOT, load_config

ARCHS = {"original": 256, "compact": 64}


def worker(conn, seed, reset_noise):
    env = BipedEnv()
    env.seed(seed)
    obs = env.reset(reset_noise)
    conn.send(obs)
    ep_ret = 0.0
    while True:
        msg = conn.recv()
        if msg is None:
            break
        action, w = msg
        nxt, r, term, trunc, info = env.step(action, w)
        ep_ret += r
        done_info = None
        store = nxt
        if term or trunc:
            done_info = (ep_ret, env.steps, info["x"])
            ep_ret = 0.0
            nxt = env.reset(reset_noise)
        conn.send((store, r, term, nxt, done_info))
    env.close()


def evaluate(actor, env, device, episodes, seed, noise):
    """Politica determinista con perturbacion inicial sembrada; velocidad por desplazamiento (H17)."""
    env.seed(seed)
    rets, speeds, lens, falls = [], [], [], 0
    for _ in range(episodes):
        obs, ret, info = env.reset(noise), 0.0, None
        while True:
            with torch.no_grad():
                a = actor.deterministic(torch.as_tensor(obs, device=device)[None])[0].cpu().numpy()
            obs, r, term, trunc, info = env.step(a)
            ret += r
            if term or trunc:
                break
        rets.append(ret)
        lens.append(env.steps * env.ctrl_dt)
        speeds.append(info["x"] / (env.steps * env.ctrl_dt))
        falls += bool(term)
    return {"return": float(np.mean(rets)), "return_std": float(np.std(rets)), "vx": float(np.mean(speeds)),
            "ep_len_s": float(np.mean(lens)), "falls": falls}


def train(a):
    random.seed(a.seed)
    np.random.seed(a.seed)
    torch.manual_seed(a.seed)
    cfg = load_config()
    device = "cuda" if torch.cuda.is_available() and not a.cpu else "cpu"
    out = ROOT / "models" / a.arch / (a.tag or f"seed{a.seed}")
    out.mkdir(parents=True, exist_ok=True)

    conns, procs = [], []
    for i in range(a.workers):
        parent, child = mp.Pipe()
        pr = mp.Process(target=worker, args=(child, a.seed * 1000 + i, a.reset_noise), daemon=True)
        pr.start()
        conns.append(parent)
        procs.append(pr)
    obs = np.stack([c.recv() for c in conns])

    env_eval = BipedEnv(max_steps=cfg["episode"]["eval_steps"])
    q_home = np.zeros(12)
    q_home[[3, 9]] = -0.1  # rodilla apenas flexionada: a=+1 exacto es inalcanzable con tanh
    agent = SAC(ARCHS[a.arch], device)
    agent.actor.init_output(env_eval.controller.action_for(q_home))
    replay = Replay(a.buffer, 36, 12, device)

    (out / "run.json").write_text(json.dumps({
        "args": vars(a), "config": cfg, "python": platform.python_version(), "torch": torch.__version__,
        "numpy": np.__version__, "pybullet_api": p.getAPIVersion(), "device": device,
        "gpu": torch.cuda.get_device_name(0) if device == "cuda" else None, "cpu": platform.processor()}, indent=1))
    log = open(out / "train_log.csv", "w", newline="", buffering=1)
    writer = csv.writer(log)
    writer.writerow(["steps", "phase", "wall_s", "train_return", "train_len", "eval_return", "eval_std", "eval_vx", "eval_len_s", "eval_falls", "alpha"])

    steps, best, t0, recent, next_eval = 0, -np.inf, time.time(), [], a.eval_every
    while steps < a.steps:
        w, phase = phase_weights(steps, cfg)
        if steps < a.random_steps:
            home = env_eval.controller.action_for(q_home)
            actions = np.clip(home + np.random.normal(0, 0.3, (a.workers, 12)), -1, 1).astype(np.float32)
        else:
            actions = agent.act(obs)
        for c, act in zip(conns, actions):
            c.send((act, w))
        if len(replay) >= a.batch:  # el GPU aprende mientras los workers simulan
            for _ in range(a.workers):
                agent.update(replay, a.batch)
        res = [c.recv() for c in conns]
        stored = np.stack([r[0] for r in res])
        replay.add_batch(torch.as_tensor(obs, device=device), torch.as_tensor(actions, device=device),
                         torch.tensor([[r[1]] for r in res], dtype=torch.float32, device=device),
                         torch.as_tensor(stored, device=device),
                         torch.tensor([[float(r[2])] for r in res], device=device))
        obs = np.stack([r[3] for r in res])
        steps += a.workers
        recent += [r[4] for r in res if r[4]]

        if steps >= next_eval:
            next_eval += a.eval_every
            m = evaluate(agent.actor, env_eval, device, a.eval_episodes, 12345, a.reset_noise)
            tr = np.mean([x[0] for x in recent]) if recent else float("nan")
            tl = np.mean([x[1] for x in recent]) if recent else float("nan")
            recent = []
            wall = time.time() - t0
            writer.writerow([steps, phase, round(wall, 1), round(tr, 2), round(tl, 1), round(m["return"], 2), round(m["return_std"], 2),
                             round(m["vx"], 4), round(m["ep_len_s"], 3), m["falls"], round(agent.log_alpha.exp().item(), 4)])
            print(f"{steps:>9,} P{phase} {steps / wall:6.0f}/s tr {tr:8.1f} len {tl:5.0f} | ev R {m['return']:8.1f} vx {m['vx']:+.3f} ep {m['ep_len_s']:.2f}s falls {m['falls']}/{a.eval_episodes} a {agent.log_alpha.exp().item():.3f}", flush=True)
            state = {"actor": agent.actor.state_dict(), "hidden": ARCHS[a.arch], "steps": steps, "eval": m}
            torch.save(state, out / "last.pt")
            if m["return"] > best:
                best = m["return"]
                torch.save(state, out / "best.pt")
    for c in conns:
        c.send(None)
    for pr in procs:
        pr.join(timeout=10)
    print("fin", steps, "mejor", best, flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--arch", choices=ARCHS, required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--steps", type=int, default=3_000_000)
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--buffer", type=int, default=1_000_000)
    ap.add_argument("--random-steps", type=int, default=25_000)  # articulo: 5000 por worker
    ap.add_argument("--eval-every", type=int, default=20_000)
    ap.add_argument("--eval-episodes", type=int, default=5)
    ap.add_argument("--reset-noise", type=float, default=0.02)
    ap.add_argument("--tag", default="")
    ap.add_argument("--cpu", action="store_true")
    train(ap.parse_args())
