// Driver INA226 para una placa monitora aparte: el medidor nunca corre en el dispositivo medido.
#pragma once
#include <stdint.h>

#include "driver/i2c_master.h"
#include "esp_err.h"

typedef struct {
    i2c_master_dev_handle_t dev;
    float shunt_ohm;
    float current_lsb;
} ina226_t;

// conv_code y avg_code son los campos del registro de configuracion (hoja de datos, tabla 7-5).
esp_err_t ina226_init(ina226_t *d, i2c_master_bus_handle_t bus, uint8_t addr, float shunt_ohm, float max_current_a,
                      uint8_t avg_code, uint8_t conv_code);
esp_err_t ina226_read(ina226_t *d, float *bus_v, float *current_a);
