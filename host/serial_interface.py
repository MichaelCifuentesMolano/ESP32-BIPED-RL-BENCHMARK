"""Enlace host y dispositivo sobre cualquier transporte con write, read y in_waiting: pyserial o VirtualESP32."""
import time
from dataclasses import dataclass, field

from host import protocol as pr


@dataclass
class LinkStats:
    sent: int = 0
    received: int = 0
    timeouts: int = 0
    stale: int = 0
    reconnects: int = 0
    errors: list = field(default_factory=list)


class DeviceTimeout(Exception):
    pass


def open_serial(port, baud=921600):
    import serial  # solo necesario con hardware
    s = serial.Serial(None, baud, timeout=0, write_timeout=0.1)
    s.port = port
    # DTR y RTS en reposo antes de abrir: el circuito de autoreinicio de las DevKit deja EN e IO0 altos, sin reinicio
    # ni modo de grabacion. pyserial los activa por defecto al abrir y la placa podria reiniciarse en mitad de la medida.
    s.dtr = s.rts = False
    s.open()
    s.reset_input_buffer()
    return s


class DeviceLink:
    def __init__(self, transport, reopen=None, timeout_s=0.015, experiment_id=0):
        self.t, self.reopen, self.timeout_s, self.experiment_id = transport, reopen, timeout_s, experiment_id
        self.parser = pr.response_parser()
        self.seq = 0
        self.stats = LinkStats()

    @property
    def crc_errors(self):
        return self.parser.crc_errors

    def _log(self, msg):
        self.stats.errors.append((time.time(), msg))
        del self.stats.errors[:-1000]

    def reconnect(self):
        if self.reopen is None:
            return False
        try:
            self.t = self.reopen()
        except OSError as e:
            self._log(f"reconexion fallida: {e}")
            return False
        self.parser = pr.response_parser()
        self.stats.reconnects += 1
        return True

    def infer(self, obs, model_id):
        """Una inferencia. Devuelve dict con acciones y tiempos; lanza DeviceTimeout si no hay respuesta valida a tiempo."""
        self.seq = (self.seq + 1) & 0xFFFFFFFF
        t0 = time.perf_counter()
        frame = pr.encode_request(model_id, self.experiment_id, self.seq, int(t0 * 1e6), obs)
        try:
            self.t.write(frame)
        except OSError as e:
            self._log(f"escritura: {e}")
            self.reconnect()
            raise DeviceTimeout("escritura fallida") from e
        self.stats.sent += 1
        deadline = t0 + self.timeout_s
        while True:
            try:
                n = self.t.in_waiting
                chunk = self.t.read(n) if n else b""
            except OSError as e:
                self._log(f"lectura: {e}")
                self.reconnect()
                raise DeviceTimeout("lectura fallida") from e
            for f in self.parser.feed(chunk) if chunk else ():
                _, status, seq, infer_us, free_heap, *actions = f
                if seq != self.seq:  # respuesta tardia de un ciclo ya perdido
                    self.stats.stale += 1
                    continue
                t1 = time.perf_counter()
                self.stats.received += 1
                return {"seq": seq, "status": status, "actions": actions, "infer_us": infer_us, "free_heap": free_heap,
                        "round_trip_us": (t1 - t0) * 1e6}
            if time.perf_counter() >= deadline:
                self.stats.timeouts += 1
                raise DeviceTimeout(f"seq {self.seq}")
