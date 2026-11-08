#include "bench_timing.h"

#include "driver/gpio.h"
#include "esp_timer.h"
#include "sdkconfig.h"

// Pines libres en ESP32-DevKitC y ESP32-S3-DevKitC, sin funcion de arranque. Confirmar con la placa real.
#define PIN_INFERENCE GPIO_NUM_4
#define PIN_FRAME GPIO_NUM_5

void bench_timing_init(void)
{
    gpio_config_t cfg = {.pin_bit_mask = (1ULL << PIN_INFERENCE) | (1ULL << PIN_FRAME), .mode = GPIO_MODE_OUTPUT};
    ESP_ERROR_CHECK(gpio_config(&cfg));
    gpio_set_level(PIN_INFERENCE, 0);
    gpio_set_level(PIN_FRAME, 0);
}

uint32_t bench_now_us(void) { return (uint32_t)esp_timer_get_time(); }
void bench_sync_inference(int level) { gpio_set_level(PIN_INFERENCE, level); }
void bench_sync_frame(int level) { gpio_set_level(PIN_FRAME, level); }
