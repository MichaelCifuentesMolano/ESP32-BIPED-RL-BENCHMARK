// Tiempo y senales GPIO para el analizador logico.
#pragma once
#include <stdint.h>

void bench_timing_init(void);
uint32_t bench_now_us(void);
void bench_sync_inference(int level);  // alto mientras corre policy_run
void bench_sync_frame(int level);      // alto desde la trama recibida hasta enviada la respuesta
