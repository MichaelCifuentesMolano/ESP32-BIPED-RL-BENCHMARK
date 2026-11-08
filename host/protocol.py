"""Protocolo binario host y ESP32. Definicion normativa; firmware/communication/protocol.h es su espejo.

Little-endian, empaquetado, sin relleno. CRC-16/CCITT-FALSE sobre todo lo que sigue a la sincronia.

Peticion (164 bytes):   A5 5A | tipo=1 | model_id u8 | experiment_id u16 | seq u32 | timestamp_us u64 | 36 x f32 | crc u16
Respuesta (66 bytes):   5A A5 | tipo=2 | status u8 | seq u32 | infer_us u32 | free_heap u32 | 12 x f32 | crc u16
"""
import struct

SYNC_REQ, SYNC_RESP = b"\xA5\x5A", b"\x5A\xA5"
T_REQUEST, T_RESPONSE, T_INFO_REQUEST, T_INFO_RESPONSE = 1, 2, 3, 4
REQ_BODY = struct.Struct("<BBHIQ36f")
RESP_BODY = struct.Struct("<BBIII12f")
REQ_SIZE = 2 + REQ_BODY.size + 2
RESP_SIZE = 2 + RESP_BODY.size + 2

STATUS_OK, STATUS_BAD_MODEL, STATUS_NON_FINITE = 0, 1, 2


def crc16(data, crc=0xFFFF):
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def encode_request(model_id, experiment_id, seq, timestamp_us, obs):
    if len(obs) != 36:
        raise ValueError("se esperan 36 observaciones")
    body = REQ_BODY.pack(T_REQUEST, model_id, experiment_id, seq & 0xFFFFFFFF, timestamp_us, *map(float, obs))
    return SYNC_REQ + body + struct.pack("<H", crc16(body))


def encode_response(status, seq, infer_us, free_heap, actions):
    if len(actions) != 12:
        raise ValueError("se esperan 12 acciones")
    body = RESP_BODY.pack(T_RESPONSE, status, seq & 0xFFFFFFFF, infer_us, free_heap, *map(float, actions))
    return SYNC_RESP + body + struct.pack("<H", crc16(body))


class FrameParser:
    """Reensambla tramas de un flujo de bytes; se resincroniza tras basura o CRC invalido."""

    def __init__(self, sync, body):
        self.sync, self.body, self.size = sync, body, 2 + body.size + 2
        self.buf = bytearray()
        self.crc_errors = 0
        self.bytes_dropped = 0

    def feed(self, data):
        self.buf += data
        frames = []
        while True:
            i = self.buf.find(self.sync)
            if i < 0:
                keep = 1 if self.buf[-1:] == self.sync[:1] else 0
                self.bytes_dropped += len(self.buf) - keep
                del self.buf[:len(self.buf) - keep]
                return frames
            self.bytes_dropped += i
            del self.buf[:i]
            if len(self.buf) < self.size:
                return frames
            payload = bytes(self.buf[2:self.size - 2])
            (crc,) = struct.unpack_from("<H", self.buf, self.size - 2)
            if crc16(payload) == crc:
                frames.append(self.body.unpack(payload))
                del self.buf[:self.size]
            else:
                self.crc_errors += 1
                del self.buf[:1]  # la sincronia pudo ser falsa: buscar la siguiente dentro de esta misma ventana


def request_parser():
    return FrameParser(SYNC_REQ, REQ_BODY)


def response_parser():
    return FrameParser(SYNC_RESP, RESP_BODY)
