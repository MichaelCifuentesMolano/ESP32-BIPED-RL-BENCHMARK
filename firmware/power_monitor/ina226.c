#include "ina226.h"

#define REG_CONFIG 0x00
#define REG_BUS 0x02
#define REG_CURRENT 0x04
#define REG_CALIBRATION 0x05
#define BUS_LSB_V 0.00125f

static esp_err_t write16(ina226_t *d, uint8_t reg, uint16_t v)
{
    uint8_t b[3] = {reg, (uint8_t)(v >> 8), (uint8_t)v};
    return i2c_master_transmit(d->dev, b, sizeof(b), 100);
}

static esp_err_t read16(ina226_t *d, uint8_t reg, int16_t *v)
{
    uint8_t b[2];
    esp_err_t e = i2c_master_transmit_receive(d->dev, &reg, 1, b, 2, 100);
    if (e == ESP_OK) *v = (int16_t)((b[0] << 8) | b[1]);
    return e;
}

esp_err_t ina226_init(ina226_t *d, i2c_master_bus_handle_t bus, uint8_t addr, float shunt_ohm, float max_current_a,
                      uint8_t avg_code, uint8_t conv_code)
{
    i2c_device_config_t cfg = {.dev_addr_length = I2C_ADDR_BIT_LEN_7, .device_address = addr, .scl_speed_hz = 400000};
    esp_err_t e = i2c_master_bus_add_device(bus, &cfg, &d->dev);
    if (e != ESP_OK) return e;
    d->shunt_ohm = shunt_ohm;
    d->current_lsb = max_current_a / 32768.0f;
    uint16_t cal = (uint16_t)(0.00512f / (d->current_lsb * shunt_ohm));
    e = write16(d, REG_CALIBRATION, cal);
    if (e != ESP_OK) return e;
    // Modo continuo de shunt y bus (0b111), misma conversion para ambos.
    uint16_t config = (uint16_t)(0x4000 | (avg_code & 7) << 9 | (conv_code & 7) << 6 | (conv_code & 7) << 3 | 7);
    return write16(d, REG_CONFIG, config);
}

esp_err_t ina226_read(ina226_t *d, float *bus_v, float *current_a)
{
    int16_t bus, cur;
    esp_err_t e = read16(d, REG_BUS, &bus);
    if (e == ESP_OK) e = read16(d, REG_CURRENT, &cur);
    if (e != ESP_OK) return e;
    *bus_v = (uint16_t)bus * BUS_LSB_V;
    *current_a = cur * d->current_lsb;
    return ESP_OK;
}
