# Pendientes para la proxima sesion

Corte: 2026-11-08, 15:00. Para retomar, pedir: "lee documentation/PENDIENTES.md y sigue con el proyecto".

## 1. Estado

Entrenamiento (6 corridas) y `run_all` terminados y revisados el 2026-11-08: registros completos y sin NaN, 90 pruebas correctas,
paridad en QEMU de ambas placas con el firmware nuevo. Resultados escritos en `documentation/informe_final.md`, seccion 5.
Historial de la matriz en `results/training/matrix.log` y en git.

**Firmware nuevo:** `firmware/inference/models_generated.c` ya lleva los modelos entrenados de la semilla 0. El ESP32 de COM5 tiene
grabado el anterior: reflashear antes de cualquier medicion y repetir la paridad en silicio.

## 2. Tareas sin hardware, en orden

1. [x] Terminar la matriz de entrenamiento. Terminada 2026-11-08 2:50 a. m., 6 `done.txt`. Original semilla 2 camina a ~0.5 m/s
   al final (5 episodios); el original varia mucho entre semillas, el compacto no.
2. [x] `run_all --seeds 0 1 2`: 2026-11-08, 12:43 a 14:45, sin errores. Registro en `results/run_all.log`.
3. [x] `results/report/tables.md` y las cuatro figuras revisados. Los puntos que parecen faltar en dos figuras estan encimados
   (valores casi iguales), no perdidos.
4. [x] 60, 100 y 140 N separan resultados tambien en el original: las caidas suben con la fuerza en los 6 modelos y 3 semillas.
   B07 no separa formatos (ninguna diferencia significativa tras Bonferroni).
5. [x] `pytest -q`: 90 correctas, antes y despues de `run_all`.
6. [x] `documentation/informe_final.md` completado (secciones 5 y 6). Corregido: decia que `environment.yml` se habia probado en
   un entorno limpio, sin evidencia de ello; y que el barrido de B07 separa formatos.
7. [ ] Probar `environment.yml` en un entorno limpio (lineas de `torch` y `ziglang` sin verificar).
8. [x] Actualizar la memoria del proyecto.

## 3. Guia de conexion de hardware: escrita

Hecha el 2026-11-07: `documentation/guia_conexion_hardware.md`. Lo que depende del ejemplar fisico esta marcado **[CONFIRMAR]**;
revisarlo cuando lleguen las placas y quitar las marcas.

**Hardware del usuario (en camino):** ESP-WROOM-32 USB-C (MercadoLibre, objetivo ESP32 clasico), ESP32-S3 DevKit **N16R8**
(objetivo S3; 16 MB flash, PSRAM 8 MB octal como la N8R8 del articulo; desviacion declarada), un ESP32 clasico propio de reserva,
INA226 I2C 0-36 V, FT232RL USB a TTL 3.3/5 V, analizador 8 canales 24 MHz. Tiene fuente regulada y multimetro.
Decidido: la placa que no se mide lee el INA226, y se invierten. El FT232RL lleva UART0 en B03 (sin USB de la placa, sin VCC).
Firmware y `host/qemu_device.py` ya configurados a 16 MB para el S3.

Riesgo abierto: en B03 el puente USB de la placa sigue unido a UART0 y puede chocar con el FT232RL. Se prueba en el paso 6.4 de la
guia; si falla, mover el protocolo a UART1 (cambio de firmware).

## 4. Tareas que requieren hardware

**2026-11-07, ESP32 clasico (ESP-WROOM-32, D0WD-V3 v3.1, CH340 en COM5), con el entrenamiento cargando el PC:**
- Grabado y paridad en silicio: `ok`, 6 modelos, error max 2.3e-6 FP32 y 1.2e-7 enteros, 0 perdidas (`results/firmware/hw_parity_esp32.json`).
- B01 (mediana de inferencia): original 41.2 / 25.6 / 14.2 ms, compacto 1.40 / 0.73 / 0.54 ms (FP32 / INT16 / INT8). Ida y vuelta
  unos 5.4 ms mas. Plazo de 20 ms: compacto 100 %, original INT8 79 %, original FP32 e INT16 0 %.
- Causa: pesos `static const` en flash leidos por la cache de 32 KB; el original FP32 (313 KB) ni cabe en la SRAM libre (299 KB).
- Repetir B04 y B05 con el PC libre: la ida y vuelta puede estar inflada por la carga.
- **Decision abierta (D7):** dejar los pesos en flash (despliegue estandar, como TFLite Micro) o copiar a SRAM los que quepan.

Nada de esto se ha ejecutado. QEMU y el ESP32 virtual no son medicion.

- [ ] **Falta codigo para B03:** `firmware/power_monitor` es solo el controlador del INA226, nunca probado en un chip real. No existe la
  aplicacion de la placa medidora, ni pines I2C definidos, ni el registro de muestras que alimenta `benchmark/energy/energy.py`.
  Hay que escribirla cuando se conozca el montaje.
- [ ] Grabar el firmware en ambas placas y repetir la paridad contra Python en silicio real. Falta apuntar
  `host/qemu_device.py` a un puerto serie (cambio pequeno).
- [ ] Comprobar PSRAM en el S3 (QEMU la reporta en 0).
- [ ] B01 latencia de inferencia, B04 jitter, B03 energia.
- [ ] B05, B06 y B07 con la placa real, para comparar con el ESP32 virtual.
- [ ] Confirmar que GPIO4 y GPIO5 estan libres en las placas concretas.

## 5. Decisiones abiertas del usuario

- **D1, rodilla:** en el URDF flexiona hacia la punta del pie. Mirar el ARON real; si difiere, usar copia adaptada del URDF, declararlo y
  reentrenar. Todo lo entrenado hasta ahora usa el URDF sin cambios.
- **Barrido de B07:** se cambio de 60 N a 60, 100 y 140 N sin consultarlo. Confirmar que sirve al articulo.
- **ESP-DL:** no evaluado. Decidir si entra en el alcance.
- **RBIPEDO no tiene licencia:** se leyo, no se copio ni ejecuto. Confirmar con Kevin antes de reutilizar su codigo.
- **Manuscrito:** avisar a los autores de las inconsistencias del informe de fase 1 (seccion "Fuera de alcance"), como el Exp. 4, que
  entro a fase 3 en 160 k y no en 1.6 M.
- **Git:** resuelto 2026-11-07. Repositorio local sin remoto. `.gitattributes` con `* -text` para no alterar el SHA-256 del URDF.
  Las corridas en curso (`models/*/seed*` sin `done.txt`) no se suben hasta terminar.

## 6. Datos utiles

- Entorno: `conda activate latiniot`. ESP-IDF 5.5.1 en `~/esp/esp-idf`; compilar con `firmware\build_all.ps1` desde PowerShell, no Git Bash.
- Ensayo provisional, compacto semilla 0, 5 episodios, datos ya borrados: INT8 camina igual que FP32 (0.61 m/s). A 120 N caen 2 a 4 de 8
  episodios. Sirve de referencia para detectar algo raro, no para citar.
- El error maximo alto en cuantizacion (0.53 en INT16) viene de muestras fuera del rango de calibracion, no de un fallo aritmetico.
