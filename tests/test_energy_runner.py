"""B03 sin hardware: formato de la medidora y cadena completa con una medidora simulada de potencia conocida."""
import time

import numpy as np
import pytest

from host import energy_runner as er
from host.serial_interface import DeviceLink
from host.virtual_esp32 import VirtualESP32


def test_meter_frame_roundtrip_and_units():
    p = er.meter_parser()
    junk = b"\x00\xC3\xff" + er.encode_meter_frame(er.T_SAMPLE, 0x40, 123, -400, 4000)
    bad = bytearray(er.encode_meter_frame(er.T_SAMPLE, 0x40, 124, 1, 1))
    bad[6] ^= 1
    frames = p.feed(junk + bytes(bad) + er.encode_meter_frame(er.T_SAMPLE, 0x41, 125, 4000, 3999))
    assert [f[1] for f in frames] == [0x40, 0x41] and p.crc_errors == 1
    t, v, i = er.to_si([f[2] for f in frames], [f[3] for f in frames], [f[4] for f in frames], 0.1)
    assert v[0] == pytest.approx(5.0) and i[0] == pytest.approx(-0.01) and i[1] == pytest.approx(0.1)


def test_meter_clock_wraps():
    t, _, _ = er.to_si([2**32 - 1000, 500], [0, 0], [0, 0], 0.1)
    assert t[1] - t[0] == pytest.approx(1500e-6)


class FakeMeter:
    """Bus de 5 V; corriente base 50 mA, mas 20 mA mientras la placa recibio una trama hace menos de 50 ms."""

    def __init__(self, dut, rate_hz=2000):
        self.dut, self.rate, self.t0 = dut, rate_hz, time.perf_counter()
        self.sent = 0

    def _due(self):
        return int((time.perf_counter() - self.t0) * self.rate) - self.sent

    @property
    def in_waiting(self):
        return max(self._due(), 0) * 14

    def read(self, n):
        out = bytearray()
        busy = time.perf_counter() - self.dut.last_write < 0.05
        for _ in range(n // 14):
            amps = 0.07 if busy else 0.05
            out += er.encode_meter_frame(er.T_SAMPLE, 0x40, int(self.sent * 1e6 / self.rate), round(amps * 0.1 / er.SHUNT_LSB_V), 4000)
            self.sent += 1
        return bytes(out)


class TrackedDUT(VirtualESP32):
    last_write = -1.0

    def write(self, data):
        self.last_write = time.perf_counter()
        return super().write(data)


def test_b03_chain_recovers_known_power():
    z = np.zeros
    layers = [(z((8, 36), np.float32), z(8, np.float32)), (z((8, 8), np.float32), z(8, np.float32)), (z((12, 8), np.float32), z(12, np.float32))]
    dut = TrackedDUT({0: ("fp32", layers)}, infer_us=0)
    obs = np.zeros((4, 36), np.float32)
    s, _ = er.run(DeviceLink(dut, timeout_s=0.5), er.MeterReader(FakeMeter(dut)), [("compact", "fp32", 0)], {"compact": obs},
                  0.1, idle_s=0.8, active_s=0.8, rate_hz=50, margin_s=0.15)
    seg = s["segments"]["compact_fp32"]
    assert s["idle_power_w"] == pytest.approx(0.25, rel=0.01)
    assert abs(s["idle_drift_w"]) < 1e-3
    assert seg["attributable_power_w"] == pytest.approx(0.10, rel=0.03)
    assert seg["inferences_per_s"] == pytest.approx(50, rel=0.1)
    assert seg["energy_per_inference_attributable_j"] == pytest.approx(0.10 / seg["inferences_per_s"], rel=0.03)
    assert seg["lost"] == 0 and seg["sample_rate_hz"] == pytest.approx(2000, rel=0.05)


def test_missing_sensor_is_reported():
    class NoSensor:
        in_waiting = 14

        def read(self, n):
            return er.encode_meter_frame(er.T_NO_DEVICE, 0, 0, 0, 0)

    r = er.MeterReader(NoSensor())
    r.start()
    with pytest.raises(RuntimeError, match="INA226"):
        er.wait_samples(r, timeout_s=0.3)
    r.stop.set()
