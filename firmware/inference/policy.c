// Inferencia MLP 36-H-H-12. Aritmetica definida en reinforcement_learning/evaluation/quantization.py.
#include "policy.h"

#include <math.h>
#include <stddef.h>

static float f_a[POLICY_MAX_HIDDEN], f_b[POLICY_MAX_HIDDEN];
static int32_t i_a[POLICY_MAX_HIDDEN], i_b[POLICY_MAX_HIDDEN];
static int64_t last_acc[POLICY_ACT_DIM];

const int64_t *policy_debug_last_acc(void) { return last_acc; }

const policy_model_t *policy_find(uint8_t id)
{
    for (int i = 0; i < policy_model_count; i++) {
        if (policy_models[i]->id == id) return policy_models[i];
    }
    return NULL;
}

static void run_f32(const policy_model_t *m, const float *obs, float *actions)
{
    const float *x = obs;
    float *y = f_a;
    for (int l = 0; l < 3; l++) {
        const policy_layer_t *ly = &m->layers[l];
        const float *w = ly->w, *b = ly->b;
        float *dst = l == 2 ? actions : y;
        for (int o = 0; o < ly->out; o++) {
            const float *row = w + (size_t)o * ly->in;
            float acc = b[o];
            for (int i = 0; i < ly->in; i++) acc += row[i] * x[i];
            dst[o] = l == 2 ? tanhf(acc) : (acc > 0.0f ? acc : 0.0f);
        }
        x = y;
        y = y == f_a ? f_b : f_a;
    }
}

static inline int32_t requant(int64_t acc, int32_t mult, uint8_t shift, int32_t qmax)
{
    // Desplazamiento aritmetico, garantizado por GCC y Clang; coincide con >> de numpy.
    int64_t v = (acc * mult + ((int64_t)1 << (shift - 1))) >> shift;
    return v < 0 ? 0 : (v > qmax ? qmax : (int32_t)v);  // ReLU fusionada
}

// Las activaciones viven en int32 para compartir buffers; los pesos conservan su ancho en flash.
#define INT_LAYER(NAME, WTYPE, ACC)                                                                        \
    static void NAME(const policy_layer_t *ly, const int32_t *x, int32_t *y, int32_t qmax, int last)       \
    {                                                                                                      \
        const WTYPE *w = ly->w;                                                                            \
        const int64_t *b = ly->b;                                                                          \
        for (int o = 0; o < ly->out; o++) {                                                                \
            const WTYPE *row = w + (size_t)o * ly->in;                                                     \
            ACC acc = 0;                                                                                   \
            for (int i = 0; i < ly->in; i++) acc += (ACC)row[i] * x[i];                                    \
            int64_t total = (int64_t)acc + b[o];                                                           \
            if (last) last_acc[o] = total;                                                                 \
            else y[o] = requant(total, ly->mult[o], ly->shift[o], qmax);                                   \
        }                                                                                                  \
    }

INT_LAYER(layer_i8, int8_t, int32_t)    // |acc| <= 127 * 127 * 256 cabe en int32
INT_LAYER(layer_i16, int16_t, int64_t)  // 32767^2 * 256 no cabe en int32

static void run_int(const policy_model_t *m, const float *obs, float *actions)
{
    const float qmax = (float)m->qmax;
    for (int i = 0; i < POLICY_OBS_DIM; i++) {
        float v = rintf(obs[i] * m->inv_input_scale[i]);
        i_a[i] = (int32_t)(v > qmax ? qmax : (v < -qmax ? -qmax : v));
    }
    const int32_t *x = i_a;
    int32_t *y = i_b;
    for (int l = 0; l < 3; l++) {
        if (m->format == POLICY_I8) layer_i8(&m->layers[l], x, y, m->qmax, l == 2);
        else layer_i16(&m->layers[l], x, y, m->qmax, l == 2);
        x = y;
        y = y == i_a ? i_b : i_a;
    }
    const float *s = m->layers[2].out_scale;
    for (int o = 0; o < POLICY_ACT_DIM; o++) actions[o] = tanhf((float)last_acc[o] * s[o]);
}

int policy_run(const policy_model_t *m, const float *obs, float *actions)
{
    for (int i = 0; i < POLICY_OBS_DIM; i++) {
        if (!isfinite(obs[i])) return -1;
    }
    if (m->format == POLICY_F32) run_f32(m, obs, actions);
    else run_int(m, obs, actions);
    return 0;
}
