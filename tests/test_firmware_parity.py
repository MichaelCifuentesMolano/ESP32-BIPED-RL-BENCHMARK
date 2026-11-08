"""Fase 7: el C del firmware, compilado para el PC, contra la referencia Python."""
import importlib.util
import struct
import subprocess
import sys

import numpy as np
import pytest

from analysis import export_models as ex
from host import protocol as pr
from reinforcement_learning.evaluation import quantization as qz
from simulation.simulation_config import ROOT

pytestmark = pytest.mark.skipif(importlib.util.find_spec("ziglang") is None, reason="sin compilador C para el PC")
FW = ROOT / "firmware"


@pytest.fixture(scope="module")
def build(tmp_path_factory):
    """Modelos deterministas propios: la prueba no depende del entrenamiento en curso."""
    tmp = tmp_path_factory.mktemp("parity")
    r = np.random.default_rng(1)
    calib = (r.normal(0, 1, (3000, 36)) * np.r_[np.ones(12), np.full(12, 6.0), np.full(12, 0.5)]).astype(np.float32)
    models = {}
    parts, names = [], []
    for arch, hidden in ex.ARCHS.items():
        layers = ex.random_actor(hidden)
        for fmt in ex.FORMATS:
            q = None if fmt == "fp32" else qz.quantize(layers, calib, fmt)
            src, name = ex.emit_model(arch, fmt, layers, q)
            parts.append(src)
            names.append(name)
            models[ex.model_id(arch, fmt)] = (fmt, layers, q)
    gen = tmp / "models_test.c"
    table = ", ".join(f"&{n}" for n in names)
    gen.write_text('#include <stddef.h>\n#include "policy.h"\n' + "".join(parts) +
                   f"const policy_model_t *const policy_models[] = {{{table}}};\nconst int policy_model_count = {len(names)};\n", encoding="utf8")
    exe = tmp / "parity.exe"
    subprocess.run([sys.executable, "-m", "ziglang", "cc", "-O2", "-fno-fast-math", "-ffp-contract=off",
                    "-I", str(FW / "inference/include"), "-I", str(FW / "communication/include"),
                    str(ROOT / "tests/parity_main.c"), str(FW / "inference/policy.c"), str(FW / "communication/protocol.c"),
                    str(gen), "-o", str(exe)], check=True, capture_output=True, timeout=240)
    return exe, models, calib, tmp


def int_hidden_output(q, obs):
    """Acumuladores enteros de la ultima capa segun la referencia Python."""
    x = qz.quantize_input(obs, q)
    for ly in q["layers"][:-1]:
        acc = x @ ly["w"].T.astype(np.int64) + ly["b"]
        x = np.clip((acc * ly["mult"] + (np.int64(1) << (ly["shift"] - 1))) >> ly["shift"], 0, q["qmax"])
    last = q["layers"][-1]
    return x @ last["w"].T.astype(np.int64) + last["b"]


def test_inference_matches_python(build):
    exe, models, calib, tmp = build
    obs = calib[:400]
    (tmp / "obs.bin").write_bytes(obs.tobytes())
    subprocess.run([str(exe), "infer", str(tmp / "obs.bin"), str(tmp / "out.bin")], check=True, timeout=120)
    rec = np.dtype([("a", "<f4", 12), ("acc", "<i8", 12)])
    out = np.fromfile(tmp / "out.bin", rec).reshape(len(obs), len(models))
    for mid, (fmt, layers, q) in models.items():
        got = out[:, mid]
        if fmt == "fp32":
            assert np.abs(got["a"] - qz.forward_fp32(layers, obs)).max() < 1e-4
        else:
            assert np.array_equal(got["acc"], int_hidden_output(q, obs)), f"modelo {mid}: enteros distintos"
            assert np.abs(got["a"] - qz.forward_quant(q, obs)).max() < 2e-6


def test_protocol_stream_matches_python(build):
    """Flujo con basura y una trama corrupta: el parser C responde byte a byte lo que espera el host."""
    exe, models, calib, tmp = build
    stream, expected = bytearray(b"\x00\xA5\x13"), bytearray()
    for seq, mid in enumerate((0, 2, 5, 9)):
        obs = calib[seq]
        frame = pr.encode_request(mid, 7, seq, 1000 + seq, obs)
        if seq == 1:
            bad = bytearray(frame)
            bad[40] ^= 0x10
            stream += bad
        stream += frame
        if mid in models:
            fmt, layers, q = models[mid]
            acc_ok = qz.forward_fp32(layers, obs) if fmt == "fp32" else qz.forward_quant(q, obs)
            expected += struct.pack("<B", 0) + np.asarray(acc_ok, "<f4").tobytes()
        else:
            expected += struct.pack("<B", pr.STATUS_BAD_MODEL) + bytes(48)
    (tmp / "s.bin").write_bytes(bytes(stream))
    r = subprocess.run([str(exe), "proto", str(tmp / "s.bin"), str(tmp / "r.bin")], check=True, capture_output=True, text=True, timeout=60)
    assert "crc_errors=1" in r.stdout
    frames = pr.response_parser().feed((tmp / "r.bin").read_bytes())
    assert [f[2] for f in frames] == [0, 1, 2, 3]
    assert [f[3] for f in frames] == [123] * 4
    i = 0
    for f in frames:
        status, actions = expected[i], np.frombuffer(bytes(expected[i + 1:i + 49]), "<f4")
        assert f[1] == status and np.abs(np.array(f[5:], np.float32) - actions).max() < 1e-4
        i += 49
