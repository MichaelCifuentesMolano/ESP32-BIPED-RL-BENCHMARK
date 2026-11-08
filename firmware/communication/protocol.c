#include "protocol.h"

#include <string.h>

uint16_t proto_crc16(const uint8_t *data, size_t len)
{
    uint16_t crc = 0xFFFF;
    while (len--) {
        crc ^= (uint16_t)(*data++) << 8;
        for (int i = 0; i < 8; i++) crc = crc & 0x8000 ? (uint16_t)((crc << 1) ^ 0x1021) : (uint16_t)(crc << 1);
    }
    return crc;
}

void proto_parser_init(proto_parser_t *p) { memset(p, 0, sizeof(*p)); }

// Descarta bytes hasta la siguiente sincronia posible dentro del buffer.
static void resync(proto_parser_t *p)
{
    size_t i = 1;
    while (i < p->len) {
        if (p->buf[i] == 0xA5 && (i + 1 == p->len || p->buf[i + 1] == 0x5A)) break;
        i++;
    }
    p->dropped_bytes += (uint32_t)i;
    p->len -= i;
    memmove(p->buf, p->buf + i, p->len);
}

int proto_parser_feed(proto_parser_t *p, uint8_t byte, proto_request_t *out)
{
    p->buf[p->len++] = byte;
    for (;;) {
        if (p->len >= 1 && p->buf[0] != 0xA5) { resync(p); if (p->len == 0) return 0; continue; }
        if (p->len >= 2 && p->buf[1] != 0x5A) { resync(p); if (p->len == 0) return 0; continue; }
        if (p->len < PROTO_REQ_SIZE) return 0;
        uint16_t crc;
        memcpy(&crc, p->buf + 2 + PROTO_REQ_BODY, 2);  // Xtensa y x86 son little-endian
        if (proto_crc16(p->buf + 2, PROTO_REQ_BODY) != crc) {
            p->crc_errors++;
            resync(p);
            continue;
        }
        const uint8_t *b = p->buf + 2;
        out->type = b[0];
        out->model_id = b[1];
        memcpy(&out->experiment_id, b + 2, 2);
        memcpy(&out->seq, b + 4, 4);
        memcpy(&out->timestamp_us, b + 8, 8);
        memcpy(out->obs, b + 16, sizeof(out->obs));
        p->len = 0;
        return 1;
    }
}

void proto_encode_response(uint8_t *out, uint8_t type, uint8_t status, uint32_t seq, uint32_t infer_us,
                           uint32_t free_heap, const float *values)
{
    out[0] = 0x5A;
    out[1] = 0xA5;
    uint8_t *b = out + 2;
    b[0] = type;
    b[1] = status;
    memcpy(b + 2, &seq, 4);
    memcpy(b + 6, &infer_us, 4);
    memcpy(b + 10, &free_heap, 4);
    memcpy(b + 14, values, 48);
    uint16_t crc = proto_crc16(b, PROTO_RESP_BODY);
    memcpy(b + PROTO_RESP_BODY, &crc, 2);
}
