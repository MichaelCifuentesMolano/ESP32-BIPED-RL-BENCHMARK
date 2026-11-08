"""Corre en secuencia la matriz de entrenamiento: misma configuracion y presupuesto para ambas arquitecturas.

  python -m reinforcement_learning.training.run_matrix --seeds 0 1 2 --steps 3000000
"""
import argparse
import subprocess
import sys

from simulation.simulation_config import ROOT

ap = argparse.ArgumentParser()
ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
ap.add_argument("--archs", nargs="+", default=["compact", "original"])
ap.add_argument("--steps", type=int, default=3_000_000)
a = ap.parse_args()
for seed in a.seeds:  # semilla afuera: primero queda un par completo comparable
    for arch in a.archs:
        out = ROOT / "models" / arch / f"seed{seed}"
        if (out / "done.txt").exists():
            continue
        print("==", arch, seed, flush=True)
        r = subprocess.run([sys.executable, "-m", "reinforcement_learning.training.train", "--arch", arch,
                            "--seed", str(seed), "--steps", str(a.steps)], cwd=ROOT)
        if r.returncode:
            sys.exit(r.returncode)
        (out / "done.txt").write_text("ok")
