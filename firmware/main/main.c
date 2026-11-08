// Servidor de inferencia por UART: recibe observaciones, ejecuta la politica, devuelve acciones.
#include <string.h>

#include "bench_timing.h"
#include "driver/uart.h"
#include "esp_chip_info.h"
#include "esp_flash.h"
#include "esp_heap_caps.h"
#include "esp_idf_version.h"
#include "esp_log.h"
#include "esp_system.h"
#include "policy.h"
#include "protocol.h"
#include "sdkconfig.h"

#define BENCH_UART UART_NUM_0
#define BENCH_BAUD 921600

static const char *TAG = "bench";

static void send_info(const proto_request_t *rq, uint8_t *tx)
{
    esp_chip_info_t chip;
    esp_chip_info(&chip);
    uint32_t flash = 0;
    esp_flash_get_size(NULL, &flash);
    // Tabla numerica fija; host/hil_controller.py la traduce. Valores enteros exactos en float32.
    float v[12] = {
        chip.model, chip.cores, chip.revision, CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ,
        flash / 1024.0f, heap_caps_get_total_size(MALLOC_CAP_SPIRAM) / 1024.0f,
        heap_caps_get_total_size(MALLOC_CAP_INTERNAL) / 1024.0f, heap_caps_get_free_size(MALLOC_CAP_INTERNAL) / 1024.0f,
        ESP_IDF_VERSION_MAJOR, ESP_IDF_VERSION_MINOR, ESP_IDF_VERSION_PATCH, policy_model_count,
    };
    proto_encode_response(tx, PROTO_T_INFO_RESPONSE, PROTO_STATUS_OK, rq->seq, 0, esp_get_minimum_free_heap_size(), v);
    uart_write_bytes(BENCH_UART, tx, PROTO_RESP_SIZE);
}

static void handle(const proto_request_t *rq, uint8_t *tx)
{
    float actions[POLICY_ACT_DIM] = {0};
    uint8_t status = PROTO_STATUS_OK;
    uint32_t infer_us = 0;
    bench_sync_frame(1);
    const policy_model_t *m = policy_find(rq->model_id);
    if (m == NULL) {
        status = PROTO_STATUS_BAD_MODEL;
    } else {
        bench_sync_inference(1);
        uint32_t t0 = bench_now_us();
        int r = policy_run(m, rq->obs, actions);
        infer_us = bench_now_us() - t0;
        bench_sync_inference(0);
        if (r != 0) status = PROTO_STATUS_NON_FINITE;
    }
    proto_encode_response(tx, PROTO_T_RESPONSE, status, rq->seq, infer_us, esp_get_free_heap_size(), actions);
    uart_write_bytes(BENCH_UART, tx, PROTO_RESP_SIZE);
    bench_sync_frame(0);
}

void app_main(void)
{
    uart_config_t cfg = {.baud_rate = BENCH_BAUD, .data_bits = UART_DATA_8_BITS, .parity = UART_PARITY_DISABLE,
                         .stop_bits = UART_STOP_BITS_1, .flow_ctrl = UART_HW_FLOWCTRL_DISABLE, .source_clk = UART_SCLK_DEFAULT};
    ESP_ERROR_CHECK(uart_driver_install(BENCH_UART, 1024, 512, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(BENCH_UART, &cfg));
    bench_timing_init();

    static proto_parser_t parser;
    static proto_request_t rq;
    static uint8_t rx[256], tx[PROTO_RESP_SIZE];
    proto_parser_init(&parser);
    ESP_LOGI(TAG, "listo, %d modelos", policy_model_count);
    for (;;) {
        int n = uart_read_bytes(BENCH_UART, rx, sizeof(rx), 1);
        for (int i = 0; i < n; i++) {
            if (!proto_parser_feed(&parser, rx[i], &rq)) continue;
            if (rq.type == PROTO_T_INFO_REQUEST) send_info(&rq, tx);
            else if (rq.type == PROTO_T_REQUEST) handle(&rq, tx);
        }
    }
}
