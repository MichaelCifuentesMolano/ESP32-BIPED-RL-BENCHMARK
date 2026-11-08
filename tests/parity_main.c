// Arnes de paridad: ejecuta en el PC exactamente el firmware de inferencia y protocolo.
//   parity infer <obs.bin> <out.bin>   por observacion y modelo: 12 float + 12 int64
//   parity proto <in.bin> <out.bin>    flujo de bytes de peticiones; responde como el firmware, con infer_us y heap fijos
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "policy.h"
#include "protocol.h"

static unsigned char *load(const char *path, long *size)
{
    FILE *f = fopen(path, "rb");
    if (!f) exit(2);
    fseek(f, 0, SEEK_END);
    *size = ftell(f);
    fseek(f, 0, SEEK_SET);
    unsigned char *b = malloc((size_t)*size + 1);
    if (fread(b, 1, (size_t)*size, f) != (size_t)*size) exit(3);
    fclose(f);
    return b;
}

int main(int argc, char **argv)
{
    if (argc != 4) return 1;
    long size;
    unsigned char *in = load(argv[2], &size);
    FILE *out = fopen(argv[3], "wb");
    float act[POLICY_ACT_DIM];
    if (!strcmp(argv[1], "infer")) {
        long n = size / (POLICY_OBS_DIM * 4);
        for (long i = 0; i < n; i++) {
            float obs[POLICY_OBS_DIM];
            memcpy(obs, in + i * POLICY_OBS_DIM * 4, sizeof(obs));
            for (int m = 0; m < policy_model_count; m++) {
                if (policy_run(policy_models[m], obs, act) != 0) return 4;
                fwrite(act, 4, POLICY_ACT_DIM, out);
                fwrite(policy_debug_last_acc(), 8, POLICY_ACT_DIM, out);
            }
        }
    } else {
        static proto_parser_t p;
        proto_request_t rq;
        unsigned char tx[PROTO_RESP_SIZE];
        proto_parser_init(&p);
        for (long i = 0; i < size; i++) {
            if (!proto_parser_feed(&p, in[i], &rq)) continue;
            const policy_model_t *m = policy_find(rq.model_id);
            unsigned char status = PROTO_STATUS_OK;
            memset(act, 0, sizeof(act));
            if (!m) status = PROTO_STATUS_BAD_MODEL;
            else if (policy_run(m, rq.obs, act) != 0) { status = PROTO_STATUS_NON_FINITE; memset(act, 0, sizeof(act)); }
            proto_encode_response(tx, PROTO_T_RESPONSE, status, rq.seq, 123, 456, act);
            fwrite(tx, 1, PROTO_RESP_SIZE, out);
        }
        printf("crc_errors=%u\n", (unsigned)p.crc_errors);
    }
    fclose(out);
    return 0;
}
