# Guia para medir con hardware real

Paso a paso completo, con montajes y revision antes de energizar: `guia_conexion_hardware.md`.

Todo lo anterior a esta guia se verifico sin placa. Latencia, jitter y energia reales solo salen de aqui.

## 1. Compilar y grabar

    powershell -File firmware\build_all.ps1
    python -m analysis.export_models --seed 0     # antes, si cambian los modelos
    . $HOME\esp\esp-idf\export.ps1
    cd firmware
    idf.py -B build_esp32 -p COMx flash           # o build_esp32s3

Cada placa se identifica sola: `read_device_info` registra chip, revision, frecuencia, flash, PSRAM y SRAM.

**Primera comprobacion:** en el ESP32-S3 N16R8 `psram_kb` debe dar unos 8192. Si da 0, la PSRAM no inicio; QEMU no permite probarlo.

## 2. Conexion

| Senal | Pin | Uso |
|---|---|---|
| UART0 | Puente USB de la placa, 921600 baudios | Protocolo |
| GPIO4 | Canal 0 del analizador | Alto durante `policy_run` |
| GPIO5 | Canal 1 del analizador | Alto de trama recibida a respuesta enviada |
| GND | GND comun | Referencia |

Confirmar que GPIO4 y GPIO5 estan libres en la placa concreta. En el S3 con PSRAM octal no usar GPIO 26 a 37.

## 3. Medidas

    python -m host.experiment_runner --group B01 --port COMx --platform esp32
    python -m host.experiment_runner --group B04 --port COMx --platform esp32 --samples 100000
    python -m host.experiment_runner --group B05 --port COMx --platform esp32
    python -m host.experiment_runner --group B06 --port COMx --platform esp32 --episodes 50
    python -m host.experiment_runner --group B07 --port COMx --platform esp32 --episodes 50 --push-n 60   # repetir con 100 y 140

Para B05: Windows no es un sistema de tiempo real y el controlador USB agrupa paquetes. Hay que declarar el latency timer del
puerto. El analizador en GPIO5 separa lo que aporta el ESP32 de lo que aporta el host.

## 4. Energia (B03)

El medidor corre en una placa aparte, nunca en la medida.

1. Alimentar la placa bajo prueba con la fuente regulada, a traves del INA226 en el lado alto, sin el USB de datos si la placa lo permite.
2. Registrar un tramo en reposo y otro con inferencia sostenida a 50 Hz, de al menos 60 s cada uno.
3. Calcular con `benchmark/energy/energy.py`.

**Limites que hay que respetar en el articulo**
- El INA226 no resuelve una inferencia individual. La energia por inferencia sale de la diferencia de potencia media entre tramos.
- La medida es de la placa completa, incluido el puente USB y el regulador. Lo atribuible a la inferencia es solo la diferencia.
- Para ver el pulso de una inferencia hace falta otro instrumento (shunt y osciloscopio).
- Calibrar el shunt con el multimetro y declarar la incertidumbre.
