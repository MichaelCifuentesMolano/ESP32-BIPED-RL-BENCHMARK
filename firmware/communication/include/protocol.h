// Espejo de host/protocol.py, que es la definicion normativa. Sin dependencias de ESP-IDF.
#pragma once
#include <stddef.h>
#include <stdint.h>

#define PROTO_T_REQUEST 1
#define PROTO_T_RESPONSE 2
#define PROTO_T_INFO_REQUEST 3
#define PROTO_T_INFO_RESPONSE 4
#define PROTO_STATUS_OK 0
#define PROTO_STATUS_BAD_MODEL 1
#define PROTO_STATUS_NON_FINITE 2

#define PROTO_REQ_BODY 160
#define PROTO_REQ_SIZE (2 + PROTO_REQ_BODY + 2)
#define PROTO_RESP_BODY 62
#define PROTO_RESP_SIZE (2 + PROTO_RESP_BODY + 2)

typedef struct {
    uint8_t type, model_id;
    uint16_t experiment_id;
    uint32_t seq;
    uint64_t timestamp_us;
    float obs[36];
} proto_request_t;

typedef struct {
    uint8_t buf[PROTO_REQ_SIZE];
    size_t len;
    uint32_t crc_errors, dropped_bytes;
} proto_parser_t;

uint16_t proto_crc16(const uint8_t *data, size_t len);
void proto_parser_init(proto_parser_t *p);

// Consume un byte. Devuelve 1 cuando out contiene una peticion valida.
int proto_parser_feed(proto_parser_t *p, uint8_t byte, proto_request_t *out);

// Escribe PROTO_RESP_SIZE bytes en out.
void proto_encode_response(uint8_t *out, uint8_t type, uint8_t status, uint32_t seq, uint32_t infer_us,
                           uint32_t free_heap, const float *values);
