// Placa medidora de B03: lee el INA226 sin pausa y envia muestras crudas por UART0 (USB de esta placa).
// Trama (14 bytes): C3 3C | tipo u8 | direccion u8 | t_us u32 | shunt i16 | bus u16 | crc16 CCITT-FALSE
// host/energy_runner.py es la definicion normativa del formato y hace la conversion a unidades.
#include <string.h>

#include "driver/i2c_master.h"
#include "driver/uart.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "ina226.h"
#include "protocol.h"
#include "sdkconfig.h"

#if CONFIG_IDF_TARGET_ESP32
#define PIN_SDA 21
#define PIN_SCL 22
#else
#define PIN_SDA 8
#define PIN_SCL 9
#endif
#define METER_UART UART_NUM_0
#define METER_BAUD 921600
#define T_SAMPLE 1
#define T_NO_DEVICE 2
#define T_READ_ERROR 3
#define CONV_140US 0
#define AVG_1 0

static void send(uint8_t type, uint8_t addr, int16_t shunt, uint16_t bus)
{
    uint8_t f[14] = {0xC3, 0x3C, type, addr};
    uint32_t t = (uint32_t)esp_timer_get_time();
    memcpy(f + 4, &t, 4);
    memcpy(f + 8, &shunt, 2);
    memcpy(f + 10, &bus, 2);
    uint16_t crc = proto_crc16(f + 2, 10);
    memcpy(f + 12, &crc, 2);
    uart_write_bytes(METER_UART, f, sizeof(f));
}

void app_main(void)
{
    uart_config_t ucfg = {.baud_rate = METER_BAUD, .data_bits = UART_DATA_8_BITS, .parity = UART_PARITY_DISABLE,
                          .stop_bits = UART_STOP_BITS_1, .flow_ctrl = UART_HW_FLOWCTRL_DISABLE, .source_clk = UART_SCLK_DEFAULT};
    ESP_ERROR_CHECK(uart_driver_install(METER_UART, 256, 4096, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(METER_UART, &ucfg));

    i2c_master_bus_config_t bcfg = {.i2c_port = I2C_NUM_0, .sda_io_num = PIN_SDA, .scl_io_num = PIN_SCL,
                                    .clk_source = I2C_CLK_SRC_DEFAULT, .glitch_ignore_cnt = 7,
                                    .flags.enable_internal_pullup = true};
    i2c_master_bus_handle_t bus;
    ESP_ERROR_CHECK(i2c_new_master_bus(&bcfg, &bus));

    uint8_t addr;
    while ((addr = ina226_find(bus)) == 0) {  // sin sensor: avisar al host y reintentar, por si se conecta despues
        send(T_NO_DEVICE, 0, 0, 0);
        vTaskDelay(pdMS_TO_TICKS(500));
    }
    ina226_t dev;
    // Shunt y corriente maxima solo fijan el registro de calibracion, que no se usa: el host convierte desde el shunt crudo.
    ESP_ERROR_CHECK(ina226_init(&dev, bus, addr, 0.1f, 0.8f, AVG_1, CONV_140US));
    for (;;) {
        int16_t shunt;
        uint16_t vbus;
        if (ina226_read_raw(&dev, &shunt, &vbus) == ESP_OK) send(T_SAMPLE, addr, shunt, vbus);
        else {
            send(T_READ_ERROR, addr, 0, 0);
            vTaskDelay(1);  // sensor desconectado: no inundar el enlace
        }
    }
}
