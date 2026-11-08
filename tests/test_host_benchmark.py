"""Fases 9 y 10: bucle HIL con ESP32 virtual, metricas y energia con senales sinteticas."""
import json

import numpy as np
import pytest

from benchmark.energy.energy import energy_per_inference, ina226_can_resolve, integrate_energy, mean_power
from host import protocol as pr
from host.data_logger import ExperimentLog, deadline_stats, experiment_id, latency_stats
from host.hil_controller import read_device_info, run_episode
from host.serial_interface import DeviceLink
from host.virtual_esp32 import VirtualESP32
from reinforcement_learning.evaluation import quantization as qz
from simulation.pybullet_env import BipedEnv


def small_policy():
    """Politica que manda siempre a la postura de pie: basta para ejercitar el bucle completo."""
    env = BipedEnv()
    target = np.clip(env.controller.action_for(np.zeros(12)), -0.99, 0.99)
    env.close()
    z = np.zeros
    return [(z((8, 36), np.float32), z(8, np.float32)), (z((8, 8), np.float32), z(8, np.float32)), (z((12, 8), np.float32), np.arctanh(target).astype(np.float32))]


def test_hil_episode_equals_direct_loop():
    """La misma politica por el enlace y directa deben dar el mismo episodio: el enlace no altera la dinamica."""
    layers = small_policy()
    env = BipedEnv(max_steps=30)
    r = run_episode(env, DeviceLink(VirtualESP32({0: ("fp32", layers)}, infer_us=0), timeout_s=0.5), 0, 0.0)
    obs = env.reset(0.0)
    while True:
        obs, _, term, trunc, info = env.step(qz.forward_fp32(layers, obs))
        if term or trunc:
            break
    env.close()
    assert not any(c["missed"] for c in r["cycles"])
    assert r["distance_m"] == pytest.approx(info["x"], abs=1e-6)


def test_timing_components_are_recorded():
    layers = small_policy()
    env = BipedEnv(max_steps=10)
    r = run_episode(env, DeviceLink(VirtualESP32({0: ("fp32", layers)}, infer_us=300, simulate_wire=True), timeout_s=0.5), 0, 0.0)
    env.close()
    c = r["cycles"][-1]
    assert c["infer_us"] == 300 and c["transfer_us"] > 2000 and c["host_us"] > 0
    assert c["cycle_us"] >= c["round_trip_us"] + c["host_us"] - 1000


def test_lost_cycles_hold_last_action_and_count():
    layers = small_policy()
    env = BipedEnv(max_steps=20)
    link = DeviceLink(VirtualESP32({0: ("fp32", layers)}, infer_us=0, p_drop=0.5, seed=2), timeout_s=0.001)
    r = run_episode(env, link, 0, 0.0)
    env.close()
    missed = sum(c["missed"] for c in r["cycles"])
    assert 0 < missed < len(r["cycles"]) and missed == link.stats.timeouts


def test_push_is_applied_in_loop():
    layers = small_policy()

    def run(push):
        env = BipedEnv(max_steps=15)
        r = run_episode(env, DeviceLink(VirtualESP32({0: ("fp32", layers)}, infer_us=0), timeout_s=0.5), 0, 0.0, push)
        env.close()
        return r["cycles"][-1]["x"]

    assert abs(run((2, [200.0, 0, 0], 0.1)) - run(None)) > 0.01


class CannedTransport:
    """Responde a la peticion de identidad con una trama fija, como lo hace main.c."""

    def __init__(self, values):
        self.values, self.reply = values, b""

    def write(self, data):
        seq = pr.request_parser().feed(data)[0][3]
        body = pr.RESP_BODY.pack(pr.T_INFO_RESPONSE, 0, seq, 0, 12345, *self.values)
        self.reply = pr.SYNC_RESP + body + pr.struct.pack("<H", pr.crc16(body))

    @property
    def in_waiting(self):
        return len(self.reply)

    def read(self, n):
        out, self.reply = self.reply, b""
        return out


def test_device_info_is_decoded_by_name():
    values = [9.0, 2, 0, 240, 8192, 8192, 400, 300, 5, 5, 1, 6]
    info = read_device_info(DeviceLink(CannedTransport(values)))
    assert info["chip_model"] == 9 and info["cpu_mhz"] == 240 and info["psram_kb"] == 8192
    assert (info["idf_major"], info["idf_minor"], info["idf_patch"]) == (5, 5, 1) and info["min_free_heap"] == 12345


# ---- metricas ----

def test_latency_stats():
    s = latency_stats(np.arange(1, 101))
    assert (s["n"], s["mean"], s["max"]) == (100, 50.5, 100)
    assert s["median"] == 50.5 and s["p99"] == pytest.approx(99.01)


def test_deadline_counts_consecutive_runs():
    c = [10, 30, 30, 10, 30, 30, 30, 10]
    s = deadline_stats(c, deadline_us=20)
    assert s["misses"] == 5 and s["max_consecutive_misses"] == 3 and s["met_percent"] == pytest.approx(37.5)


def test_deadline_includes_lost_cycles():
    s = deadline_stats([10, 10, 10, 10], deadline_us=20, missed=[0, 1, 1, 0])
    assert s["misses"] == 2 and s["max_consecutive_misses"] == 2


def test_no_misses():
    assert deadline_stats([1, 2, 3], 20)["max_consecutive_misses"] == 0


def test_experiment_log_marks_virtual_as_not_measured(tmp_path, monkeypatch):
    import host.data_logger as d
    monkeypatch.setattr(d, "ROOT", tmp_path)
    log = ExperimentLog("B01", ["a"], model="compact", platform="virtual", precision="int8", seed=0, repetitions=1)
    log.row(1)
    out = log.close({"x": 1})
    meta = json.loads((out / "result.json").read_text(encoding="utf8"))
    assert meta["measured_on_hardware"] is False and meta["group"] == "B01" and (out / "raw.csv").exists()


def test_experiment_log_requires_metadata():
    with pytest.raises(ValueError):
        ExperimentLog("B01", ["a"], model="x")


def test_experiment_id_is_stable():
    assert experiment_id("B01", a=1, b=2) == experiment_id("B01", b=2, a=1) != experiment_id("B01", a=2, b=2)


# ---- energia, con senales de energia conocida ----

def test_integrate_known_energy():
    t = np.linspace(0, 2, 2001)
    assert integrate_energy(t, np.full_like(t, 5.0), np.full_like(t, 0.1)) == pytest.approx(1.0)
    assert integrate_energy(t, np.full_like(t, 2.0), t) == pytest.approx(4.0)
    assert mean_power(t, np.full_like(t, 5.0), np.full_like(t, 0.1)) == pytest.approx(0.5)


def test_attributable_energy_removes_idle():
    t = np.linspace(0, 10, 1000)
    r = energy_per_inference((t, np.full_like(t, 5.0), np.full_like(t, 0.12)), (t, np.full_like(t, 5.0), np.full_like(t, 0.10)), 50)
    assert r["board_power_w"] == pytest.approx(0.6) and r["attributable_power_w"] == pytest.approx(0.1)
    assert r["energy_per_inference_attributable_j"] == pytest.approx(0.002)
    assert r["energy_per_cycle_board_j"] == pytest.approx(0.012)


def test_ina226_refuses_fast_pulse():
    assert not ina226_can_resolve(300e-6, 280e-6)
    assert ina226_can_resolve(60.0, 0.01)


def test_fall_rates_sum_seeds_per_force():
    from analysis.make_report import fall_rates
    row = lambda seed, push, falls: {"model": "compact", "precision": "int8", "seed": seed, "push": push, "summary": {"falls": falls, "episodes": 50}}
    t = fall_rates([row(0, 100.0, 3), row(1, 100.0, 4), row(0, 140.0, 9)])
    assert t[("compact", "int8")][100.0] == [7, 100] and t[("compact", "int8")][140.0] == [9, 50]
