# ESP32-BIPED-RL-BENCHMARK

Testbed para evaluar politicas SAC (36-256-256-12 y 36-64-64-12) en FP32, INT16 e INT8 sobre ESP32-WROOM-32 y ESP32-S3 N16R8 (el articulo usa N8R8),
con un bipedo 3D de 12 GdL simulado en PyBullet y conectado por UART (hardware in the loop).

Estado y tareas: `documentation/PENDIENTES.md`. Informes: `documentation/fase1_inspeccion_urdf.md`, `documentation/informe_final.md`. Con placa: `documentation/guia_conexion_hardware.md` (paso a paso) y `documentation/guia_hardware.md` (resumen).
Formato numerico: `documentation/formato_cuantizacion.md`.

    conda env create -f environment.yml
    conda activate latiniot
    python -m pytest -q
    python -m reinforcement_learning.training.run_matrix --seeds 0 1 2 --steps 3000000
    python -m benchmark.run_all --seeds 0 1 2      # observaciones, cuantizacion, B05 a B07, firmware, QEMU, informe

El firmware necesita ESP-IDF 5.5.1 en `~/esp/esp-idf` (`firmware/build_all.ps1`). Las tablas y figuras salen en `results/report/`.

`robot/urdf/biped.urdf` es copia byte a byte de `../biped.urdf`; una prueba fija su SHA-256.
Sin placa, B05 a B07 usan un ESP32 virtual con la aritmetica exacta del firmware: el desempeno es valido, los tiempos del
dispositivo no. B01, B03 y B04 solo tienen sentido con hardware.
