"""Fases 6 y 8: cuantizacion, protocolo, enlace y ESP32 virtual."""
import numpy as np
import pytest

from host import protocol as pr
from host.serial_interface import DeviceLink, DeviceTimeout
from host.virtual_esp32 import VirtualESP32
from reinforcement_learning.evaluation import quantization as qz


def random_layers(hidden, seed=0):
    r = np.random.default_rng(seed)
    dims = [(hidden, 36), (hidden, hidden), (12, hidden)]
    return [((r.normal(0, 1 / np.sqrt(i), (o, i))).astype(np.float32), r.normal(0, 0.1, o).astype(np.float32)) for o, i in dims]


def calib(n=3000, seed=1):
    r = np.random.default_rng(seed)
    scale = np.array([1.0] * 12 + [8.0] * 12 + [0.2, 0.3, 0.3, 0.5, 2, 1, 1, 3, 3, 3, 0.5, 0.5], np.float32)
    return (r.normal(0, 1, (n, 36)) * scale).astype(np.float32)


# ---- cuantizacion ----

def test_crc_known_vector():
    assert pr.crc16(b"123456789") == 0x29B1  # CRC-16/CCITT-FALSE


@pytest.mark.parametrize("hidden", [64, 256])
def test_int16_much_closer_than_int8(hidden):
    layers, x = random_layers(hidden), calib()
    ref = qz.forward_fp32(layers, x)
    e8 = qz.action_errors(ref, qz.forward_quant(qz.quantize(layers, x, "int8"), x))
    e16 = qz.action_errors(ref, qz.forward_quant(qz.quantize(layers, x, "int16"), x))
    assert e16["mae"] < 1e-3 and e8["mae"] < 0.08
    assert e16["mae"] < e8["mae"] / 20


def test_per_feature_input_scale_protects_small_variables():
    """H20: una variable de rango 0.2 junto a una de rango 20 debe seguir distinguiendose en INT8."""
    layers, x = random_layers(64), calib()
    q = qz.quantize(layers, x, "int8")
    assert q["input_scale"][24] < q["input_scale"][12] / 10
    assert np.abs(qz.quantize_input(x, q)[:, 24]).max() >= 120


def test_quantized_values_fit_format():
    layers, x = random_layers(64), calib()
    for fmt, lim in (("int8", 127), ("int16", 32767)):
        q = qz.quantize(layers, x, fmt)
        for ly in q["layers"]:
            assert np.abs(ly["w"]).max() <= lim
        assert np.abs(qz.quantize_input(x * 100, q)).max() <= lim


def test_int16_accumulator_cannot_overflow_int64():
    layers, x = random_layers(256), calib()
    q = qz.quantize(layers, x, "int16")
    for ly in q["layers"][:-1]:
        worst = np.abs(ly["w"].astype(np.int64)).sum(1).max() * 32767 + np.abs(ly["b"]).max()
        assert float(worst) * float(ly["mult"].max()) < 2.0**63


def test_multiplier_precision():
    real = np.array([1e-6, 0.003, 0.7, 0.999])
    m, s = qz._multiplier(real)
    assert np.allclose(m / 2.0 ** s, real, rtol=2e-7)
    with pytest.raises(ValueError):
        qz._multiplier(np.array([0.0]))


def test_model_sizes_scale_with_format():
    layers, x = random_layers(256), calib()
    f, i16, i8 = qz.model_bytes(layers), qz.model_bytes(layers, qz.quantize(layers, x, "int16")), qz.model_bytes(layers, qz.quantize(layers, x, "int8"))
    assert i8 < i16 < f and i8 < 0.3 * f


# ---- protocolo ----

OBS = list(np.linspace(-1, 1, 36, dtype=np.float32))
ACT = list(np.linspace(-1, 1, 12, dtype=np.float32))


def test_frame_sizes_fit_budget():
    assert (pr.REQ_SIZE, pr.RESP_SIZE) == (164, 66)
    assert (pr.REQ_SIZE + pr.RESP_SIZE) * 10 / 921600 < 0.003


def test_round_trip_encoding():
    f = pr.request_parser().feed(pr.encode_request(3, 7, 99, 123456789012, OBS))[0]
    assert f[:5] == (pr.T_REQUEST, 3, 7, 99, 123456789012) and np.allclose(f[5:], OBS)
    g = pr.response_parser().feed(pr.encode_response(0, 99, 450, 1000, ACT))[0]
    assert g[:5] == (pr.T_RESPONSE, 0, 99, 450, 1000) and np.allclose(g[5:], ACT)


def test_wrong_lengths_rejected():
    with pytest.raises(ValueError):
        pr.encode_request(0, 0, 0, 0, OBS[:-1])
    with pytest.raises(ValueError):
        pr.encode_response(0, 0, 0, 0, ACT[:-1])


def test_parser_handles_fragments_and_garbage():
    frame = pr.encode_response(0, 1, 2, 3, ACT)
    p = pr.response_parser()
    stream = b"\x00\x5A\xFF" + frame + b"\x5A" + frame
    got = []
    for i in range(0, len(stream), 7):
        got += p.feed(stream[i:i + 7])
    assert len(got) == 2


def test_every_single_bit_flip_is_detected():
    frame = pr.encode_response(0, 1, 2, 3, ACT)
    for pos in range(2, len(frame)):
        for bit in range(8):
            bad = bytearray(frame)
            bad[pos] ^= 1 << bit
            assert pr.response_parser().feed(bytes(bad)) == []


def test_parser_recovers_after_corrupt_frame():
    good = pr.encode_response(0, 5, 2, 3, ACT)
    bad = bytearray(good)
    bad[20] ^= 0xFF
    p = pr.response_parser()
    frames = p.feed(bytes(bad) + good)
    assert len(frames) == 1 and frames[0][2] == 5 and p.crc_errors >= 1


# ---- enlace con ESP32 virtual ----

def device(**kw):
    layers, x = random_layers(64), calib(500)
    return VirtualESP32({0: ("fp32", layers), 2: ("quant", qz.quantize(layers, x, "int8"))}, infer_us=0, **kw), layers


def test_virtual_inference_matches_reference():
    dev, layers = device()
    r = DeviceLink(dev, timeout_s=0.5).infer(OBS, 0)
    assert r["status"] == pr.STATUS_OK and np.allclose(r["actions"], qz.forward_fp32(layers, np.array(OBS)), atol=1e-6)


def test_unknown_model_and_non_finite_are_reported():
    dev, _ = device()
    link = DeviceLink(dev, timeout_s=0.5)
    assert link.infer(OBS, 9)["status"] == pr.STATUS_BAD_MODEL
    assert link.infer([float("nan")] * 36, 0)["status"] == pr.STATUS_NON_FINITE


def test_lost_response_times_out_and_counts():
    dev, _ = device(p_drop=1.0)
    link = DeviceLink(dev, timeout_s=0.002)
    with pytest.raises(DeviceTimeout):
        link.infer(OBS, 0)
    assert link.stats.timeouts == 1


def test_corrupt_response_is_rejected_not_delivered():
    dev, _ = device(p_corrupt=1.0)
    link = DeviceLink(dev, timeout_s=0.003)
    with pytest.raises(DeviceTimeout):
        link.infer(OBS, 0)
    assert link.stats.received == 0


def test_late_response_is_discarded_by_sequence():
    import time
    dev, layers = device(p_late=1.0, late_s=0.01)
    link = DeviceLink(dev, timeout_s=0.002)
    with pytest.raises(DeviceTimeout):
        link.infer(OBS, 0)
    dev.p_late = 0.0
    time.sleep(0.015)
    r = link.infer(OBS, 0)
    assert r["seq"] == 2 and link.stats.stale == 1


def test_reconnect_after_port_loss():
    dev, _ = device()
    fresh, _ = device()
    link = DeviceLink(dev, reopen=lambda: fresh, timeout_s=0.5)
    dev.closed = True
    with pytest.raises(DeviceTimeout):
        link.infer(OBS, 0)
    assert link.stats.reconnects == 1
    assert link.infer(OBS, 0)["status"] == pr.STATUS_OK


def test_fault_injection_statistics_are_consistent():
    dev, _ = device(p_corrupt=0.1, p_drop=0.1, seed=3)
    link = DeviceLink(dev, timeout_s=0.001)
    ok = 0
    for _ in range(300):
        try:
            link.infer(OBS, 0)
            ok += 1
        except DeviceTimeout:
            pass
    s = link.stats
    assert ok + s.timeouts == 300 and ok == s.received
    assert 180 < ok < 270 and link.crc_errors > 0
