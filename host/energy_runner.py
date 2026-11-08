"""B03: energia por inferencia. La placa medidora lee el INA226; la placa medida recibe inferencias a ritmo fijo.

  python -m host.energy_runner --check --meter-port COM6 --shunt-ohm 0.1          # solo medidora, 5 s
  python -m host.energy_runner --dut-port COM5 --meter-port COM6 --platform esp32 --shunt-ohm 0.1

Montaje 3 de documentation/guia_conexion_hardware.md: la placa medida sin USB, datos por el FT232RL.
Orden: reposo, un tramo activo por modelo, reposo otra vez. Las muestras se asignan a cada tramo por la hora del PC,
con un margen en cada borde; la integracion usa el reloj de la medidora. La diferencia entre los dos reposos mide la deriva.

Trama de la medidora (14 bytes, definicion normativa; firmware/meter_app/main/main.c es su espejo):
  C3 3C | tipo u8 | direccion u8 | t_us u32 | shunt i16 | bus u16 | crc16 CCITT-FALSE sobre los 10 bytes centrales
"""
import argparse
import json
import struct
import threading
import time

import numpy as np

from analysis.export_models import ARCHS, FORMATS, model_id
from benchmark.energy.energy import mean_power
from host import protocol as pr
from host.data_logger import ExperimentLog
from host.hil_controller import wait_ready
from host.serial_interface import DeviceLink, DeviceTimeout, open_serial
from simulation.simulation_config import ROOT

SYNC_METER = b"\xC3\x3C"
METER_BODY = struct.Struct("<BBIhH")
T_SAMPLE, T_NO_DEVICE, T_READ_ERROR = 1, 2, 3
SHUNT_LSB_V, BUS_LSB_V = 2.5e-6, 1.25e-3


def meter_parser():
    return pr.FrameParser(SYNC_METER, METER_BODY)


def encode_meter_frame(kind, addr, t_us, shunt, bus):
    """Igual que el firmware de la medidora; lo usan las pruebas y la medidora simulada."""
    body = METER_BODY.pack(kind, addr, t_us & 0xFFFFFFFF, shunt, bus)
    return SYNC_METER + body + struct.pack("<H", pr.crc16(body))


def to_si(t_us, shunt, bus, shunt_ohm):
    """Registros crudos a (t s, V, A). El contador de 32 bits de la medidora da la vuelta cada 71.6 min."""
    t = np.asarray(t_us, np.int64)
    t = t + (np.cumsum(np.r_[0, np.diff(t) < 0]) << 32)
    return t / 1e6, np.asarray(bus, float) * BUS_LSB_V, np.asarray(shunt, float) * SHUNT_LSB_V / shunt_ohm


class MeterReader(threading.Thread):
    """Lee la medidora en segundo plano y guarda (hora PC, t_us, shunt, bus) por muestra."""

    def __init__(self, transport):
        super().__init__(daemon=True)
        self.t, self.parser, self.rows, self.stop = transport, meter_parser(), [], threading.Event()
        self.no_device = self.read_errors = 0
        self.addr = None

    def run(self):
        while not self.stop.is_set():
            n = self.t.in_waiting
            if not n:
                time.sleep(0.0005)
                continue
            now = time.perf_counter()
            for kind, addr, t_us, shunt, bus in self.parser.feed(self.t.read(n)):
                if kind == T_SAMPLE:
                    self.addr = addr
                    self.rows.append((now, t_us, shunt, bus))
                elif kind == T_NO_DEVICE:
                    self.no_device += 1
                else:
                    self.read_errors += 1

    def window(self, start, end, margin):
        """Muestras recibidas entre start + margin y end - margin (hora del PC)."""
        r = [x for x in self.rows if start + margin <= x[0] <= end - margin]
        return np.array(r, float).reshape(-1, 4)


def power_stats(seg, shunt_ohm, block_s=1.0):
    """Potencia media y su error estandar a partir de bloques de block_s segundos."""
    t, v, i = to_si(seg[:, 1].astype(np.int64), seg[:, 2], seg[:, 3], shunt_ohm)
    p = mean_power(t, v, i)
    edges = np.arange(t[0], t[-1], block_s)
    blocks = [mean_power(t[m], v[m], i[m]) for a in edges if (m := (t >= a) & (t < a + block_s)).sum() > 2]
    sem = float(np.std(blocks, ddof=1) / np.sqrt(len(blocks))) if len(blocks) > 1 else float("nan")
    return {"power_w": p, "power_sem_w": sem, "v_mean": float(v.mean()), "i_mean_a": float(i.mean()), "samples": len(t),
            "sample_rate_hz": float((len(t) - 1) / (t[-1] - t[0])), "duration_s": float(t[-1] - t[0])}, (t, v, i)


def wait_samples(reader, timeout_s=3.0):
    end = time.perf_counter() + timeout_s
    while time.perf_counter() < end and not reader.rows:
        time.sleep(0.05)
    if not reader.rows:
        why = "la medidora no encuentra el INA226 (revisar SDA, SCL, VCC y GND)" if reader.no_device else "sin datos de la medidora"
        raise RuntimeError(why)


def drive(link, mid, obs, rate_hz, duration_s):
    """Inferencias a ritmo fijo durante duration_s. Devuelve (inicio, fin, respuestas, sin respuesta)."""
    period, ok, lost = 1.0 / rate_hz, 0, 0
    start = time.perf_counter()
    k = 0
    while (t := time.perf_counter()) - start < duration_s:
        try:
            r = link.infer(obs[k % len(obs)], mid)
            ok += r["status"] == pr.STATUS_OK
            lost += r["status"] != pr.STATUS_OK
        except DeviceTimeout:
            lost += 1
        k += 1
        nxt = start + k * period
        if (d := nxt - time.perf_counter()) > 0:
            time.sleep(d)
    return start, time.perf_counter(), ok, lost


def run(link, reader, models, obs_by_arch, shunt_ohm, idle_s, active_s, rate_hz, margin_s):
    """models: lista de (arch, fmt, model_id). Devuelve resumen y muestras etiquetadas por tramo."""
    reader.start()
    wait_samples(reader)
    segs = []
    t0 = time.perf_counter()
    time.sleep(idle_s)
    segs.append(("idle_pre", None, t0, time.perf_counter(), 0, 0))
    for arch, fmt, mid in models:
        s, e, ok, lost = drive(link, mid, obs_by_arch[arch], rate_hz, active_s)
        segs.append((f"{arch}_{fmt}", mid, s, e, ok, lost))
    t0 = time.perf_counter()
    time.sleep(idle_s)
    segs.append(("idle_post", None, t0, time.perf_counter(), 0, 0))
    reader.stop.set()
    reader.join(1.0)

    stats, samples = {}, {}
    for name, mid, s, e, ok, lost in segs:
        w = reader.window(s, e, margin_s)
        if len(w) < 10:
            raise RuntimeError(f"tramo {name} con {len(w)} muestras: medidora detenida o margen demasiado grande")
        st, tvi = power_stats(w, shunt_ohm)
        if mid is not None:
            st.update(responses=ok, lost=lost, inferences_per_s=ok / (e - s))
        stats[name], samples[name] = st, tvi
    p_idle = (stats["idle_pre"]["power_w"] + stats["idle_post"]["power_w"]) / 2
    drift = stats["idle_post"]["power_w"] - stats["idle_pre"]["power_w"]
    for name, st in stats.items():
        if name.startswith("idle"):
            continue
        att = st["power_w"] - p_idle
        rate = st["inferences_per_s"]
        st.update(attributable_power_w=att, energy_per_cycle_board_j=st["power_w"] / rate if rate else float("nan"),
                  energy_per_inference_attributable_j=att / rate if rate else float("nan"))
    summary = {"idle_power_w": p_idle, "idle_drift_w": drift, "shunt_ohm": shunt_ohm, "rate_hz": rate_hz,
               "ina226_address": reader.addr, "meter_read_errors": reader.read_errors, "segments": stats,
               "resolution_note": "promedio de tramo sostenido, no medicion de una inferencia individual; "
                                  "si |idle_drift_w| es comparable a attributable_power_w, el tramo no resuelve la inferencia"}
    return summary, samples


def check_meter(reader, shunt_ohm, seconds=5.0):
    """Paso 7.3 de la guia: con la placa medida apagada, corriente cerca de 0 y tension de bus la de la fuente."""
    reader.start()
    wait_samples(reader)
    t0 = time.perf_counter()
    time.sleep(seconds)
    reader.stop.set()
    st, _ = power_stats(reader.window(t0, time.perf_counter(), 0.0), shunt_ohm)
    st.update(ina226_address=hex(reader.addr or 0), read_errors=reader.read_errors)
    return st


def load_obs(arch, seed, n=500):
    data = ROOT / "datasets" / f"{arch}_seed{seed}.npz"
    if data.exists():
        return np.load(data)["test"][:n]
    return np.random.default_rng(seed).normal(0, 1, (n, 36)).astype(np.float32)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--meter-port", required=True)
    ap.add_argument("--dut-port")
    ap.add_argument("--platform", choices=["esp32", "esp32s3"])
    ap.add_argument("--shunt-ohm", type=float, required=True, help="valor calibrado con el multimetro (seccion 8 de la guia)")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--archs", nargs="+", default=list(ARCHS), choices=list(ARCHS))
    ap.add_argument("--idle-s", type=float, default=60.0)
    ap.add_argument("--active-s", type=float, default=60.0)
    ap.add_argument("--rate-hz", type=float, default=50.0)
    ap.add_argument("--margin-s", type=float, default=1.0)
    a = ap.parse_args()
    meter = MeterReader(open_serial(a.meter_port))
    if a.check:
        print(json.dumps(check_meter(meter, a.shunt_ohm), indent=1))
        raise SystemExit
    if not (a.dut_port and a.platform):
        ap.error("B03 necesita --dut-port y --platform")
    link = DeviceLink(open_serial(a.dut_port), timeout_s=0.5)
    info = wait_ready(link)
    print(info)
    models = [(arch, fmt, model_id(arch, fmt)) for arch in a.archs for fmt in FORMATS]
    summary, samples = run(link, meter, models, {arch: load_obs(arch, a.seed) for arch in a.archs}, a.shunt_ohm,
                           a.idle_s, a.active_s, a.rate_hz, a.margin_s)
    summary["device"] = info
    log = ExperimentLog("B03", ["segment", "t_s", "v", "i"], model="+".join(a.archs), precision="+".join(FORMATS), platform=a.platform,
                        seed=a.seed, repetitions=len(models), shunt_ohm=a.shunt_ohm, rate_hz=a.rate_hz)
    for name, (t, v, i) in samples.items():
        for row in zip(t, v, i):
            log.row(name, *(f"{x:.7g}" for x in row))
    print(log.close(summary).name, json.dumps({k: v for k, v in summary.items() if k != "segments"}))
