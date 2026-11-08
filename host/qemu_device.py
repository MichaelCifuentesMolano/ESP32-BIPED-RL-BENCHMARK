"""Corre el binario real del firmware en el QEMU de Espressif y lo compara con la referencia Python.

  python -m host.qemu_device esp32
  python -m host.qemu_device esp32s3
  python -m host.qemu_device esp32 --port COM5     # misma prueba en la placa real: results/firmware/hw_parity_esp32.json

Verifica funcion, no tiempos: QEMU no modela ciclos, asi que infer_us aqui no es una medicion.
Salida: results/firmware/qemu_<objetivo>.json
"""
import argparse
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
from host.hil_controller import wait_ready
from host.serial_interface import DeviceLink, DeviceTimeout, open_serial
from reinforcement_learning.evaluation.quantization import forward_fp32, forward_quant
from simulation.simulation_config import ROOT

HOME = Path.home()
PORT = 5599
FLASH_MB = {"esp32": 4, "esp32s3": 16}  # placa N16R8, igual a sdkconfig.defaults.esp32s3


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


def flash_image(target, build=None):
    build = build or ROOT / "firmware" / f"build_{target}"
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



def infer_retry(link, obs, mid, retries, counter):
    """En QEMU, con el equipo cargado, a veces una respuesta queda retenida hasta la siguiente peticion (medido: solo
    en corridas lentas del emulador, igual con y sin bufer de TX). Se reintenta y se cuenta; en placa real retries=0."""
    for _ in range(retries + 1):
        try:
            return link.infer(obs, mid)
        except DeviceTimeout:
            counter["timeouts"] += 1
    return None


def check(target, seed=0, per_model=40, port=None):
    """Sin port, contra QEMU. Con port, la misma prueba contra la placa real por puerto serie (paso 6.5 de la guia)."""
    proc = None if port else start_qemu(target, flash_image(target))
    note = "paridad en placa real" if port else "funcional; infer_us de QEMU no es medicion"
    report = {"target": target, "port": port, "note": note, "models": {}}
    try:
        link = DeviceLink(open_serial(port) if port else SocketTransport(PORT), timeout_s=2.0)
        retries, lost = (0 if port else 3), {"timeouts": 0}
        report["timeouts"] = lost  # en placa real cada uno es una perdida verdadera; en QEMU, reintentos
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
                resp = [infer_retry(link, o, model_id(arch, fmt), retries, lost) for o in obs]
                ok_rows = [i for i, r in enumerate(resp) if r is not None]
                got = np.array([resp[i]["actions"] for i in ok_rows], np.float32).reshape(-1, 12)
                err = float(np.abs(got - ref[ok_rows]).max()) if ok_rows else float("inf")
                report["models"][f"{arch}_{fmt}"] = {"n": len(ok_rows), "max_abs_vs_python": err}
                print(arch, fmt, report["models"][f"{arch}_{fmt}"], flush=True)
        status = lambda o, mid: (r := infer_retry(link, o, mid, retries, lost)) and r["status"]
        report["bad_model_status"] = status(np.zeros(36), 99)
        report["nan_status"] = status([float("nan")] * 36, 0)
        frame = bytearray(pr.encode_request(0, 0, 777, 0, np.zeros(36)))
        frame[50] ^= 1
        link.t.write(bytes(frame))
        report["after_corrupt_frame_status"] = status(np.ones(36), 0)
        complete = all(m["n"] == per_model for m in report["models"].values())
        report["ok"] = (complete and max(m["max_abs_vs_python"] for m in report["models"].values()) < 1e-4 and report["bad_model_status"] == pr.STATUS_BAD_MODEL
                        and report["nan_status"] == pr.STATUS_NON_FINITE and report["after_corrupt_frame_status"] == pr.STATUS_OK)
    finally:
        if proc:
            proc.kill()
            err = proc.stderr.read().decode(errors="replace")[-400:]
            if err.strip():
                report["qemu_stderr"] = err
    out = ROOT / "results" / "firmware" / (f"hw_parity_{target}.json" if port else f"qemu_{target}.json")
    out.write_text(json.dumps(report, indent=1), encoding="utf8")
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="?", default="esp32", choices=list(FLASH_MB))
    ap.add_argument("--port", help="puerto serie de la placa real; sin el, QEMU")
    a = ap.parse_args()
    r = check(a.target, port=a.port)
    print(json.dumps({k: v for k, v in r.items() if k != "models"}, indent=1))
