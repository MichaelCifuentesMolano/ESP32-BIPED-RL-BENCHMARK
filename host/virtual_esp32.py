"""ESP32 virtual: mismo protocolo y misma aritmetica que el firmware, para probar el host sin hardware.

Las latencias que reporta son un parametro de simulacion, nunca una medicion de hardware.
"""
import random
import time
from collections import deque

import numpy as np

from host import protocol as pr
from reinforcement_learning.evaluation.quantization import forward_fp32, forward_quant

BYTE_TIME_S = 10 / 921600  # 8N1


class VirtualESP32:
    def __init__(self, models, infer_us=500, seed=0, simulate_wire=False, p_corrupt=0.0, p_drop=0.0, p_late=0.0, late_s=0.05):
        """models: {model_id: ('fp32', layers) o ('quant', q)}. Las probabilidades inyectan fallos reproducibles."""
        self.models, self.infer_us, self.wire = models, infer_us, simulate_wire
        self.p_corrupt, self.p_drop, self.p_late, self.late_s = p_corrupt, p_drop, p_late, late_s
        self.rng = random.Random(seed)
        self.parser = pr.request_parser()
        self.pending = deque()  # (instante de entrega, bytes)
        self.requests = 0
        self.closed = False

    def _run(self, model_id, obs):
        kind, m = self.models[model_id]
        x = np.asarray(obs, np.float32)
        return forward_fp32(m, x) if kind == "fp32" else forward_quant(m, x)

    def write(self, data):
        if self.closed:
            raise OSError("puerto cerrado")
        now = time.perf_counter()
        for f in self.parser.feed(data):
            _, model_id, _, seq, _, *obs = f
            self.requests += 1
            if self.rng.random() < self.p_drop:
                continue
            if model_id not in self.models:
                status, actions = pr.STATUS_BAD_MODEL, [0.0] * 12
            elif not np.all(np.isfinite(obs)):
                status, actions = pr.STATUS_NON_FINITE, [0.0] * 12
            else:
                status, actions = pr.STATUS_OK, self._run(model_id, obs)
            frame = bytearray(pr.encode_response(status, seq, self.infer_us, 200_000, actions))
            if self.rng.random() < self.p_corrupt:
                frame[self.rng.randrange(2, len(frame))] ^= 1 << self.rng.randrange(8)
            delay = self.infer_us * 1e-6
            if self.wire:
                delay += (pr.REQ_SIZE + pr.RESP_SIZE) * BYTE_TIME_S
            if self.rng.random() < self.p_late:
                delay += self.late_s
            self.pending.append((now + delay, bytes(frame)))
        return len(data)

    @property
    def in_waiting(self):
        if self.closed:
            raise OSError("puerto cerrado")
        now = time.perf_counter()
        return sum(len(b) for t, b in self.pending if t <= now)

    def read(self, n):
        out = bytearray()
        now = time.perf_counter()
        while self.pending and self.pending[0][0] <= now and len(out) < n:
            out += self.pending.popleft()[1]
        return bytes(out)
