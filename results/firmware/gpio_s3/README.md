# GPIO4 y GPIO5 del ESP32-S3 con analizador logico (2026-11-11)

Montaje 2 de `documentation/guia_conexion_hardware.md`. S3 en COM8 (CH343). Analizador clon Saleae (USB 0925:3881, fx2lafw,
WinUSB por Zadig), sigrok-cli 0.8.0-git. CH1 = D0 = GPIO4, CH2 = D1 = GPIO5, CH3 = D2 = GPIO44 (RX), CH4 = D3 = GPIO43 (TX).

**Frecuencia de muestreo: 12 MHz (83 ns)**, no 24 MHz: a 24 MHz el USB de este PC corta la captura con 2 y con 4 canales.
Repetido con el analizador solo en un puerto USB 3.0 (ROOT_HUB30): 24 MHz corta 4 de 4, 16 MHz corta 2 de 3, 12 MHz completa
3 de 3. El limite es del clon con sigrok en Windows, no del hub compartido.
Disparo en el flanco de subida de D1, 3 s por captura. La del compacto se corto a 0.67 s (fx2lafw, "Device only sent").

Capturas tomadas mientras corria B01 en placa (`--archs original --samples 400`, luego `--archs compact --samples 5000`).
Ambas caen en el tramo FP32 (es el primero que corre). Resultados B01 de esas corridas: B01_b60096fc (original FP32) y
B01_a7e291b1 (compacto FP32).

| | GPIO4 mediana | B01 mediana (FP32) | GPIO5 mediana | GPIO4 dentro de GPIO5 |
|---|---|---|---|---|
| original | 20711.3 us (n 120) | 20710 us | 20777.8 us | 119/120 |
| compacto | 203.0 us (n 166) | 202 us | 254.1 us | 165/166 |

- GPIO4 coincide con el temporizador interno de B01 a 1 us. El maximo del compacto (1946 us, primera inferencia) coincide con
  el maximo de B01 (1945 us).
- El pulso que falta en "dentro de GPIO5" es el ultimo: la captura termina con GPIO5 todavia alto.
- GPIO5 menos GPIO4: unos 66 us (original) y 51 us (compacto), lo que tarda el firmware en recibir, validar y responder.
- UART a 921600 8N1 decodificado con sigrok (`-P uart:rx=D2:tx=D3:baudrate=921600`): 0 errores. Original 19680 bytes del host
  y 7920 del ESP (164 y 66 por ciclo); compacto 27175 y 10956.

Reproducir: `python -m analysis.sr_pulses results/firmware/gpio_s3/s3_original.sr`.
