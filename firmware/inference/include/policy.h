// Interfaz de inferencia. No depende de ESP-IDF ni del protocolo: compila igual en el PC para las pruebas de paridad.
#pragma once
#include <stdint.h>

#define POLICY_OBS_DIM 36
#define POLICY_ACT_DIM 12
#define POLICY_MAX_HIDDEN 256

typedef enum { POLICY_F32 = 0, POLICY_I16 = 1, POLICY_I8 = 2 } policy_format_t;

typedef struct {
    int16_t in, out;
    const void *w;           // fila por salida: float, int16_t o int8_t
    const void *b;           // float en F32, int64_t en los enteros (escala s_w[o] * s_x)
    const int32_t *mult;     // capas ocultas enteras
    const uint8_t *shift;    // capas ocultas enteras
    const float *out_scale;  // ultima capa entera
} policy_layer_t;

typedef struct {
    const char *name;
    uint8_t id;
    policy_format_t format;
    int32_t qmax;
    const float *inv_input_scale;  // enteros: 1/s_in por variable
    policy_layer_t layers[3];
} policy_model_t;

extern const policy_model_t *const policy_models[];
extern const int policy_model_count;

const policy_model_t *policy_find(uint8_t id);

// Devuelve 0 si la observacion es finita y escribe 12 acciones en [-1, 1].
int policy_run(const policy_model_t *m, const float *obs, float *actions);

// Acumuladores de la ultima capa de la ultima corrida entera, para comparar bit a bit.
const int64_t *policy_debug_last_acc(void);
