"""Corre el binario real del firmware en el QEMU de Espressif y lo compara con la referencia Python.

  python -m host.qemu_device esp32
  python -m host.qemu_device esp32s3

Verifica funcion, no tiempos: QEMU no modela ciclos, asi que infer_us aqui no es una medicion.
Salida: results/firmware/qemu_<objetivo>.json
"""
import glob
import json
import os
import select
import socket
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from analysis.export_models import ARCHS, FORMATS, model_id
from host import protocol as pr
from host.hil_controller import read_device_info
from host.serial_interface import DeviceLink
from reinforcement_learning.evaluation.quantization import forward_fp32, forward_quant
from simulation.simulation_config import ROOT

HOME = Path.home()
PORT = 5599
FLASH_MB = {"esp32": 4, "esp32s3": 8}


class SocketTransport:
    def __init__(self, port, attempts=100):
        for _ in range(attempts):
            try:
                self.s = socket.create_connection(("127.0.0.1", port), timeout=1)
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise OSError("QEMU no abrio el puerto")
        self.s.setblocking(False)
        self.buf = bytearray()

    def write(self, data):
        self.s.setblocking(True)
        self.s.sendall(data)
        self.s.setblocking(False)
        return len(data)

    @property
    def in_waiting(self):
        if select.select([self.s], [], [], 0.001)[0]:
            chunk = self.s.recv(4096)
            if not chunk:
                raise OSError("QEMU cerro el puerto")
            self.buf += chunk
        return len(self.buf)

    def read(self, n):
        out, self.buf = bytes(self.buf[:n]), self.buf[n:]
        return out


def flash_image(target):
    build = ROOT / "firmware" / f"build_{target}"
    out = build / "flash_qemu.bin"
    py = next(iter(glob.glob(str(HOME / ".espressif/python_env/idf5.5*/Scripts/python.exe"))))
    subprocess.run([py, "-m", "esptool", "--chip", target, "merge_bin", "--fill-flash-size", f"{FLASH_MB[target]}MB", "-o", str(out), "@flash_args"],
                   cwd=build, check=True, capture_output=True, timeout=120)
    return out


def start_qemu(target, image):
    exe = next(iter(glob.glob(str(HOME / ".espressif/tools/qemu-xtensa/*/qemu/bin/qemu-system-xtensa.exe"))))
    args = [exe, "-nographic", "-machine", target, "-drive", f"file={image},if=mtd,format=raw",
            "-serial", f"tcp:127.0.0.1:{PORT},server,nowait"]
    args += ["-m", "8M"] if target == "esp32s3" else ["-global", "driver=timer.esp32.timg,property=wdt_disable,value=true"]
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)


def wait_ready(link, tries=60):
    for _ in range(tries):
        try:
            return read_device_info(link)
        except Exception:
            time.sleep(0.5)
    raise TimeoutError("el firmware no respondio")


def check(target, seed=0, per_model=40):
    image = flash_image(target)
    proc = start_qemu(target, image)
    report = {"target": target, "note": "funcional; infer_us de QEMU no es medicion", "models": {}}
    try:
        link = DeviceLink(SocketTransport(PORT), timeout_s=2.0)
        report["device"] = wait_ready(link)
        rng = np.random.default_rng(seed)
        for arch in ARCHS:
            d = np.load(ROOT / "models" / arch / f"quant_seed{seed}.npz", allow_pickle=True)
            q, layers = d["q"].item(), [tuple(x) for x in d["layers"]]
            data = ROOT / "datasets" / f"{arch}_seed{seed}.npz"
            obs = np.load(data)["test"] if data.exists() else rng.normal(0, 1, (per_model, 36)).astype(np.float32)
            obs = obs[rng.integers(0, len(obs), per_model)]
            for fmt in FORMATS:
                ref = forward_fp32(layers, obs) if fmt == "fp32" else forward_quant(q[fmt], obs)
                got = np.array([link.infer(o, model_id(arch, fmt))["actions"] for o in obs], np.float32)
                report["models"][f"{arch}_{fmt}"] = {"n": per_model, "max_abs_vs_python": float(np.abs(got - ref).max())}
                print(arch, fmt, report["models"][f"{arch}_{fmt}"], flush=True)
        report["bad_model_status"] = link.infer(np.zeros(36), 99)["status"]
        report["nan_status"] = link.infer([float("nan")] * 36, 0)["status"]
        frame = bytearray(pr.encode_request(0, 0, 777, 0, np.zeros(36)))
        frame[50] ^= 1
        link.t.write(bytes(frame))
        report["after_corrupt_frame_status"] = link.infer(np.ones(36), 0)["status"]
        report["ok"] = (max(m["max_abs_vs_python"] for m in report["models"].values()) < 1e-4 and report["bad_model_status"] == pr.STATUS_BAD_MODEL
                        and report["nan_status"] == pr.STATUS_NON_FINITE and report["after_corrupt_frame_status"] == pr.STATUS_OK)
    finally:
        proc.kill()
        err = proc.stderr.read().decode(errors="replace")[-400:]
        if err.strip():
            report["qemu_stderr"] = err
    out = ROOT / "results" / "firmware" / f"qemu_{target}.json"
    out.write_text(json.dumps(report, indent=1), encoding="utf8")
    return report


if __name__ == "__main__":
    r = check(sys.argv[1] if len(sys.argv) > 1 else "esp32")
    print(json.dumps({k: v for k, v in r.items() if k != "models"}, indent=1))
