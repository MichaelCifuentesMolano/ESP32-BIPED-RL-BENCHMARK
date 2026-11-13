# Pendientes para la proxima sesion

Corte: 2026-11-12, noche. Resumen de lo que queda: seccion 7. Para retomar, pedir: "lee documentation/PENDIENTES.md y sigue con el proyecto".

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

**Hardware del usuario (todo en mano desde 2026-11-09, falta revisar las marcas [CONFIRMAR]):** ESP-WROOM-32 USB-C (MercadoLibre, objetivo ESP32 clasico), ESP32-S3 DevKit **N16R8**
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
- **Decision abierta (D7):** dejar los pesos en flash (despliegue estandar, como TFLite Micro) o copiar a SRAM los que quepan.

**2026-11-08, mismo ESP32 en COM6, PC sin carga, firmware de `run_all` (semilla 0):** grabado, paridad identica bit a bit a la
del 7/11, B01 (1 000), B04 (100 000 por modelo, 15:03 a 18:18, 0 errores de enlace) y B05 (10 episodios). Cifras en
`documentation/datos_paper.md`, seccion 5. La ida y vuelta del 7/11 no estaba inflada: el enlace cuesta 5.2 a 5.8 ms con el PC libre.
En B05 el original pierde el 100 % de los ciclos (plazo de 15 ms) y cae siempre; el compacto camina igual que en el virtual.
Registro: `results/hw_2026-11-08.log`. B01 sobrescribio las carpetas del 7/11 (mismo identificador); la version anterior esta en git.

Pendiente con placa:

- [x] B03 energia, ESP32 clasico (2026-11-12, `results/B03/B03_55b404bd`): medidora el S3 (COM8, INA226 en 0x44), enlace por
  FT232RL (COM9, latency timer 1 ms) al UART0 del clasico sin su USB. Prueba 6.4 ok: el CH340 del clasico no choca con el FT232RL
  (B01 corto por COM9 igual al de USB: `results/B01/B01_2e59b460` y vecinos de 100 muestras). Reposo 145.6 mW, deriva 0.75 mW,
  0 errores, 0 perdidas. Energia atribuible por inferencia (FP32 / INT16 / INT8): original 1.21 / 1.00 / 0.61 mJ, compacto
  0.090 / 0.085 / 0.069 mJ. En el compacto las diferencias entre formatos son del orden de la deriva: no se afirman.
  Desviaciones a declarar: (1) el pin 5V del S3 es "5Vin", solo entrada, asi que el clasico se alimenta por su pin 3V3 desde el
  3V3 del S3 a traves del INA226 (se mide sin el regulador del clasico); (2) el modulo INA226 necesita un puente de VBUS a VIN-
  para leer la tension de bus; (3) sin multimetro, shunt nominal 0.1 ohm sin calibrar (corrientes y potencias se reescalan por
  0.1/R real sin repetir); (4) muestreo real 1778 Hz, no 3500.
- [x] B03 energia, ESP32-S3 (2026-11-12, `results/B03/B03_eb26284f`): montaje invertido, medidora el clasico (COM13, 1417
  muestras/s), S3 por 3V3 desde el clasico, FT232RL a GPIO43/44. Prueba 6.4 ok tambien en el S3 (B01 corto igual al del 9/11).
  Reposo 127.0 mW, deriva 0.95 mW, 0 errores, 0 perdidas. Energia atribuible (FP32 / INT16 / INT8): original 1.42 / 0.92 /
  0.56 mJ, compacto 0.055 / 0.066 / 0.058 mJ (formatos indistinguibles). Mismas desviaciones que el clasico. Para grabar el
  clasico con el FT232RL conectado a su UART0 hay que soltar TXD y RXD: el FT232RL tapa al CH340.
  Estado de las placas al cierre: el clasico tiene `meter_app`, el S3 el firmware de benchmark.
- [x] ESP32-S3 (2026-11-09, COM8, puente CH343 1A86:55D3, chip rev. 2, firmware de 5cf27ca): grabado, paridad ok (error max 2.3e-6 FP32,
  1.2e-7 enteros, rechaza modelo inexistente, NaN y trama corrupta), PSRAM 8192 kB, flash 16 MB. B01 mediana: original 20.71 / 11.12 /
  5.89 ms, compacto 0.20 / 0.41 / 0.31 ms (FP32 / INT16 / INT8). En el S3 el compacto FP32 es mas rapido que INT16 e INT8.
  Registro: `results/hw_2026-11-09_s3.log`. El conector USB/OTG (303A:4001) no sirve: el protocolo va por el COM/UART.
- [x] ESP32-S3 B05 (2026-11-11, 10 episodios, plazo 15 ms, mismo firmware): el compacto camina igual que en el clasico
  (0.61 m/s, 0 caidas, 0 % ciclos perdidos en los 3 formatos). Original FP32: 100 % perdidos, 10 caidas (igual que el clasico).
  Original INT16: 30.3 % perdidos (11.1 ms de inferencia + unos 3.6 ms de enlace roza los 15 ms), 10 caidas. **Original INT8:
  0 % perdidos, 1 caida de 10, 0.41 m/s**: en el S3 el original solo es desplegable en INT8. Enlace medio en B05 unos 3.7 ms.
- [x] ESP32-S3 B04 (2026-11-11, 10:24 a 12:08, 100 000 por modelo, n completo en los 6): mediana original 20.71 / 11.12 / 5.89 ms,
  compacto 0.20 / 0.41 / 0.31 ms (FP32 / INT16 / INT8); p99 a 1 o 2 us de la mediana; maximos 1.9 ms en compacto FP32 y 1.2 ms
  en INT16 (picos raros). Confirma B01. Registro: `results/hw_2026-11-09_s3.log`.
- [ ] B06 y B07 en placa (opcional: B05 ya muestra que el compacto se comporta igual que en el virtual).
- [x] GPIO4 y GPIO5 del S3 con el analizador (2026-11-11, 12 MHz porque a 24 MHz el USB corta): GPIO4 coincide con B01 a 1 us
  (original FP32 20711 us, compacto FP32 203 us), GPIO4 dentro de GPIO5, UART a 921600 sin errores. `results/firmware/gpio_s3/`.
  Falta repetirlo en el ESP32 clasico si se quiere la misma verificacion alli.

## 5. Decisiones abiertas del usuario

- **Plazo de B05 (nuevo, 2026-11-08):** el host espera la accion 15 ms (`TIMEOUT_S` en `host/experiment_runner.py`), sin
  documentar hasta hoy. Con 20 ms el original INT8 cumpliria el 75 % de los ciclos en vez de 0 %. Decidir si 15 ms se mantiene
  (y se justifica en el articulo) o si se repite B05 con 20 ms como variante.

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

## 7. Lo que queda (2026-11-12)

Para el articulo (`documentation/datos_paper.md` esta al dia; lo redacta Claude Desktop):
- [ ] Decidir el plazo de B05 (15 o 20 ms) y justificarlo en el texto (seccion 5).
- [ ] Declarar las desviaciones de B03 (datos_paper, 5c.4).

Opcional, mejora la calidad pero no bloquea:
- [ ] Calibrar el shunt con multimetro (guia, seccion 8) y reescalar B03 por 0.1 / R real; no hace falta repetir.
- [ ] B03 con alimentacion por 5V (pad IN-OUT del S3 puenteado o fuente regulada) para la potencia de placa completa.
- [ ] Repetir B03 (2 o 3 corridas) si se quiere afirmar diferencias entre formatos del compacto.
- [ ] B06 y B07 en placa.
- [ ] GPIO4/5 con analizador en el ESP32 clasico.
- [ ] D7: pesos del original en SRAM o PSRAM.
- [ ] `environment.yml` en entorno limpio.
- [ ] Decisiones de la seccion 5: D1 rodilla, barrido de B07, ESP-DL, licencia de RBIPEDO, aviso al manuscrito.
