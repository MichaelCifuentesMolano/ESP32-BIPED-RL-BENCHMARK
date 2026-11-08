"""Tras el entrenamiento: observaciones, cuantizacion, benchmark sin hardware, firmware y figuras.

  python -m benchmark.run_all --seeds 0 1 2

Sin placa corre B05, B06 y B07 con el ESP32 virtual, que ejecuta la aritmetica exacta del firmware: desempeno funcional
valido, tiempos del dispositivo simulados. B01, B03 y B04 miden el dispositivo: solo tienen sentido con placa.
"""
import argparse
import subprocess
import sys

from analysis.export_models import ARCHS, export
from reinforcement_learning.evaluation.collect_observations import collect
from simulation.simulation_config import ROOT


PUSH_N = (60, 100, 140)  # medido: 60 N no tumba al compacto y 200 N casi siempre; fuera de ese tramo B07 no distingue formatos


def run(*args):
    print(">>", *args, flush=True)
    subprocess.run([sys.executable, "-m", *args], cwd=ROOT, check=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--episodes", type=int, default=50)
    a = ap.parse_args()
    for seed in sorted(a.seeds, reverse=True):  # la semilla menor queda en el firmware
        for arch in ARCHS:
            collect(arch, seed)
        export(seed)
        run("host.experiment_runner", "--group", "B06", "--seed", str(seed), "--episodes", str(a.episodes))
        for force in PUSH_N:
            run("host.experiment_runner", "--group", "B07", "--seed", str(seed), "--episodes", str(a.episodes), "--push-n", str(force))
    run("host.experiment_runner", "--group", "B05", "--seed", str(min(a.seeds)), "--episodes", "10")
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "firmware/build_all.ps1")], check=True)
    for target in ("esp32", "esp32s3"):
        run("host.qemu_device", target)
    run("analysis.make_report")
