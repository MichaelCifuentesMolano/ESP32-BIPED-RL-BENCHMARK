# Informe final: SAC cuantizado en ESP32 y ESP32-S3 para un bipedo de 12 GdL

Estado (2026-11-08): metodo, entrenamiento y benchmark sin hardware completos. Las cifras de desempeno salen de
`results/report/tables.md` (`benchmark.run_all`). En placa hay paridad y B01 en el ESP32 clasico; jitter, energia y el S3 estan
pendientes (seccion 6).

## 1. Objetivo

Medir que pierde una politica SAC de locomocion al pasar de PC a microcontrolador, en dos ejes:

- **Arquitectura del actor:** original 36-256-256-12 (la del articulo) y compacta 36-64-64-12 (propuesta).
- **Formato numerico:** FP32, INT16 e INT8 (`formato_cuantizacion.md`).

Plataformas: ESP32 clasico (ESP-WROOM-32, sin PSRAM) y ESP32-S3 N16R8. El bipedo se simula en PyBullet en el PC y la politica
corre en la placa, conectada por UART a 921600 baudios (hardware in the loop).

## 2. Montaje experimental

| Pieza | Donde | Descripcion |
|---|---|---|
| Robot | `robot/urdf/biped.urdf` | Copia byte a byte del URDF original; una prueba fija su SHA-256 |
| Simulacion | `simulation/` | PyBullet, paso de 1 ms, control a 50 Hz (20 pasos por accion), 50 iteraciones de solver, 4 subpasos |
| Entrenamiento | `reinforcement_learning/training/` | SAC, 3 M pasos, 3 semillas por arquitectura, calendario de 3 fases |
| Cuantizacion | `reinforcement_learning/evaluation/quantization.py` | Enteros simetricos, pesos por fila, activaciones calibradas con observaciones reales |
| Firmware | `firmware/` | ESP-IDF 5.5.1, los 6 modelos en una imagen, protocolo binario con CRC-16 |
| Host | `host/` | Bucle HIL, ESP32 virtual con la aritmetica exacta del firmware, registro de cada experimento |
| Energia | `firmware/meter_app`, `host/energy_runner.py` | INA226 leido por la otra placa; energia por diferencia de tramos |

Grupos del benchmark:

| Grupo | Mide | Sin placa |
|---|---|---|
| B01 | Latencia de inferencia aislada | No aplica |
| B02 | Memoria estatica del firmware | Si (tamano de la imagen) |
| B03 | Energia por inferencia | No aplica |
| B04 | Jitter con 100 000 inferencias | No aplica |
| B05 | Ciclo HIL completo: dispositivo, enlace y host | Host real; dispositivo y enlace simulados |
| B06 | Locomocion, 50 episodios por modelo y semilla | Si, desempeno valido |
| B07 | Recuperacion ante empujes de 60, 100 y 140 N | Si, desempeno valido |

## 3. Desviaciones respecto al articulo

Todas se aplican igual a ambas arquitecturas y a todas las semillas.

| Desviacion | Articulo u original | Aqui | Motivo |
|---|---|---|---|
| Amortiguamiento de tobillo | 3.0 (RBIPEDO) | 0.3 (URDF) | Con inercia de ~5e-4, 3.0 deja la junta pegada (error de seguimiento de 41 %) |
| Ganancias PD | PID_KP y PID_KD de RBIPEDO | kp 30, 150, 300, 200, 80, 30; kd 0.2, 6, 12, 8, 0.2, 0.1 | hip_roll sube de 50 a 150 para sostener el apoyo simple; kd de cadera pitch >= 16 vibra y satura |
| Termino de energia | Torque comandado | (tau/tau_max)^2 promedio del periodo de control | Con control por posicion la accion es una referencia, no un torque |
| Sesgo inicial del actor | No dice | La salida inicial apunta a la postura de pie | Con accion 0, la formula de referencia articular pone la rodilla a -75 grados |
| Ruido de reset | Sin aleatoriedad | 0.02 en la postura inicial, sembrado | Sin ruido los 5 episodios de evaluacion son el mismo (H18) |
| Criticos | 256-256 | 256-256 en ambas arquitecturas | El critico no se despliega; solo cambia el actor |
| Calendario | Tabla 6: fase 3 desde 1.6 M | 40 k / 160 k / 3 M | Es el calendario que produjo el resultado principal del articulo (H16) |
| Velocidad de evaluacion | `v_x` instantanea | Desplazamiento / duracion | La instantanea no es la medida que describe el articulo (H17) |
| Empujes en B07 | 60 N | 60, 100 y 140 N | 60 N casi no tumba al compacto; 200 N casi siempre. El barrido separa fuerzas y arquitecturas (seccion 5.3) |
| Placa S3 | N8R8 | N16R8 | Misma PSRAM (8 MB octal); solo cambia la flash, que no interviene en la inferencia |

Por eso las velocidades de este trabajo no se comparan directamente con las del articulo. La comparacion valida es entre
arquitecturas y formatos dentro de este mismo entorno.

## 4. Validacion sin hardware

- **Suite de pruebas:** 90 pruebas, todas correctas en el entorno `latiniot` (2026-11-08). Falta repetirlas en un entorno creado
  desde cero con `environment.yml`.
- **Paridad del firmware en PC:** el codigo C de inferencia, compilado en el PC, coincide con la referencia Python.
- **Paridad en QEMU:** el binario real de ambas placas en el QEMU de Espressif. Error maximo contra Python de 1e-5 en FP32 y
  de 1e-7 en enteros. Rechaza modelo inexistente, observacion NaN y trama corrupta. En QEMU con el equipo cargado, alguna
  respuesta queda retenida hasta la siguiente peticion; la prueba la reintenta y la cuenta (`timeouts` en el JSON).
- **Determinismo:** con la misma semilla, el entorno es repetible bit a bit (se corrigio la fuerza obsoleta de `restoreState`).
- **Energia:** la cadena de B03 recupera una potencia conocida inyectada por una medidora simulada, con error menor a 3 %. El
  firmware de la medidora, ejecutado en QEMU, produce tramas que el host decodifica sin errores.

## 5. Resultados sin hardware

Fuente: `results/report/tables.md` y sus cuatro figuras, generados por `benchmark.run_all --seeds 0 1 2` el 2026-11-08 (2 h, sin
errores). B05 a B07 corren con el ESP32 virtual: el desempeno es valido, los tiempos del dispositivo no.

### 5.1 Entrenamiento

Las 6 corridas terminadas (ultimos 500 k pasos, evaluacion de 5 episodios cada 20 k). "Empieza a caminar": paso de la tercera
evaluacion seguida con velocidad mayor a 0.2 m/s.

| Corrida | Velocidad (m/s) | Caidas de 5 | Empieza a caminar |
|---|---|---|---|
| compact semilla 0 | 0.53 | 0.12 | 0.80 M |
| compact semilla 1 | 0.53 | 0.04 | 1.62 M |
| compact semilla 2 | 0.56 | 0.08 | 1.64 M |
| original semilla 0 | 0.28 | 0.48 | 1.68 M |
| original semilla 1 | 0.41 | 0.12 | 1.10 M |
| original semilla 2 | 0.58 | 0.32 | 1.20 M |

El compacto es estable entre semillas (0.53 a 0.56 m/s). El original varia mucho (0.28 a 0.58 m/s) y cae mas.

`best.pt` es el maximo de 150 evaluaciones de 5 episodios y sobreestima (compacto: 0.61 a 0.63 m/s frente a 0.53 de media). Las
cifras citables son las de B06, que reevalua con 50 episodios.

### 5.2 Cuantizacion

Error de la accion frente a FP32, media +/- desviacion entre las 3 semillas:

| Actor | Formato | Parametros | MAE | Error P99.9 |
|---|---|---|---|---|
| Original | INT16 | 163 KB | 0.00057 +/- 0.00018 | 0.64 +/- 0.27 |
| Original | INT8 | 85 KB | 0.023 +/- 0.008 | 1.04 +/- 0.67 |
| Compacto | INT16 | 16 KB | 0.00026 +/- 0.00020 | 0.11 +/- 0.06 |
| Compacto | INT8 | 9 KB | 0.012 +/- 0.002 | 0.48 +/- 0.44 |

- **INT16:** el error medio es despreciable. La cola viene de las observaciones de prueba fuera del rango de calibracion (0.5 a
  0.8 %). No es un fallo aritmetico: con la semilla 0, solo recortar esas entradas al rango, en FP32, ya cambia la accion hasta
  1.96. El actor original es muy sensible fuera de lo que vio.
- **INT8:** el original tiene el doble de error medio que el compacto en las tres semillas. La cola (P99.9) varia mucho entre
  semillas: en la semilla 2 el compacto la tiene peor (1.10 frente a 0.33).
- El percentil de calibracion de las activaciones INT8 del compacto lo elige el exportador por semilla (99.99, 99.99 y 99.9).
- Este error no se traduce en peor marcha (5.3).

### 5.3 B06 y B07

B06, sin empujes, 50 episodios por modelo y semilla (150 por fila):

| Actor | Formato | Velocidad (m/s) | Caidas |
|---|---|---|---|
| Original | FP32 / INT16 / INT8 | 0.527 / 0.527 / 0.523 (+/- 0.10 entre semillas) | 10 / 5 / 12 de 150 |
| Compacto | FP32 / INT16 / INT8 | 0.614 / 0.615 / 0.613 (+/- 0.01 entre semillas) | 0 / 2 / 2 de 150 |

B07, empuje lateral de 0.1 s, episodios con caida de 150:

| Actor | Formato | 60 N | 100 N | 140 N |
|---|---|---|---|---|
| Original | FP32 / INT16 / INT8 | 24 / 25 / 22 | 51 / 63 / 60 | 104 / 111 / 105 |
| Compacto | FP32 / INT16 / INT8 | 9 / 15 / 6 | 59 / 45 / 46 | 116 / 108 / 105 |

- **Formato:** INT16 e INT8 caminan igual que FP32 en ambos actores. La velocidad media cambia menos de 0.005 m/s.
- **Arquitectura:** el compacto camina mas rapido y casi igual en las tres semillas. El original depende mucho de la semilla
  (0.41 a 0.65 m/s) y cae mas sin empujes; casi todas sus caidas de B06 son de la semilla 0.
- **B07:** las caidas suben con la fuerza en los 6 modelos y en las 3 semillas, tambien en el original. A 60 N el compacto
  resiste mejor; a 140 N los dos caen en 69 a 77 % de los episodios.
- **B07 no separa formatos.** Las diferencias entre formatos de un mismo actor no tienen un sentido fijo: a 100 N el compacto
  FP32 cae mas que sus versiones cuantizadas (59 frente a 45 y 46) y el original FP32 menos (51 frente a 63 y 60). De las 18
  comparaciones entre pares de formatos, la mayor (compacto a 60 N, INT16 15 frente a INT8 6) da z = 2.04. Con la correccion de
  Bonferroni para 18 comparaciones el umbral es z = 2.99: ninguna es significativa.
- Las velocidades de B06 son mayores que las del entrenamiento (5.1) porque B06 evalua `best.pt`, no el ultimo modelo.

### 5.4 B02 y B05

- **B02:** la imagen con los 6 modelos ocupa 642 KB de datos en flash en el esp32 y 644 KB en el S3, casi todo pesos (los
  parametros suman 615 KB). DRAM estatica: 14.7 KB en el esp32.
- **B05:** el ciclo HIL completo cumple los 20 ms en 99.9 a 100 % de los ciclos (mediana de 7 ms, P99 de 9 ms). El tiempo del
  host es real (3.6 a 4.0 ms, casi todo PyBullet). El dispositivo y el enlace estan simulados: la inferencia virtual vale
  0.5 ms en todos los modelos. **No se puede leer como que el original cumple el plazo:** en el ESP32 real su inferencia tarda
  41 ms en FP32 y 26 ms en INT16 (seccion 6). B05 hay que repetirlo en placa.
- **QEMU (2026-11-08):** el firmware nuevo, con los pesos de la semilla 0, coincide con Python en ambas placas (error maximo de
  2e-6 en FP32 y 1.2e-7 en enteros, 0 respuestas retenidas).

## 6. Pendiente con hardware

Montaje y orden en `guia_conexion_hardware.md`. El codigo esta escrito y probado sin placa; falta:

- Hecho en el ESP32 clasico (ESP-WROOM-32, D0WD-V3 v3.1), 2026-11-07: paridad en silicio (`results/firmware/hw_parity_esp32.json`)
  y B01 (`results/B01/`). Mediana de inferencia: original 41.2 / 25.6 / 14.2 ms, compacto 1.40 / 0.73 / 0.54 ms (FP32 / INT16 /
  INT8). El original solo entra en el plazo de 20 ms en INT8. Se midio con el firmware anterior a `run_all`: la latencia depende de
  la arquitectura, no del valor de los pesos, pero la paridad hay que repetirla tras grabar el firmware nuevo. Decision abierta D7: pesos en flash (actual) o en SRAM.
- Paridad y B01 en el S3, y `psram_kb` cerca de 8192.
- B04: jitter real, con el PC sin carga.
- B05 a B07 en placa, para contrastar con el ESP32 virtual.
- B03: energia. El INA226 real no se ha probado; QEMU no lo emula.
- Riesgo abierto: en B03 el puente USB de la placa medida sigue unido a UART0 y puede chocar con el FT232RL (paso 6.4 de la guia).

## 7. Limites de este trabajo

- Los tiempos del dispositivo sin placa son simulados; ninguna cifra de latencia o energia de este informe es una medicion.
- El INA226 no resuelve una inferencia individual; la energia por inferencia es la diferencia de potencia media entre tramos.
- La medida de energia incluye la placa completa, con su regulador y su puente USB; lo atribuible es solo la diferencia.
- El URDF se usa sin cambios: en el, la rodilla flexiona hacia la punta del pie (D1). Si el robot ARON real difiere, hay que usar
  una copia adaptada y reentrenar.
- RBIPEDO no tiene licencia: se leyo para reproducir el entorno, no se copio ni se ejecuto su codigo.
