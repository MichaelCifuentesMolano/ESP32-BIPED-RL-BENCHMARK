# Informe final: SAC cuantizado en ESP32 y ESP32-S3 para un bipedo de 12 GdL

Estado: metodo y validacion sin hardware completos. Las cifras de desempeno salen de `results/report/tables.md`
(`benchmark.run_all`). Las de latencia, jitter y energia requieren placa y estan pendientes (seccion 6).

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
| Empujes en B07 | 60 N | 60, 100 y 140 N | 60 N no tumba al compacto; 200 N casi siempre. El barrido separa formatos |
| Placa S3 | N8R8 | N16R8 | Misma PSRAM (8 MB octal); solo cambia la flash, que no interviene en la inferencia |

Por eso las velocidades de este trabajo no se comparan directamente con las del articulo. La comparacion valida es entre
arquitecturas y formatos dentro de este mismo entorno.

## 4. Validacion sin hardware

- **Suite de pruebas:** 90 pruebas, todas correctas en un entorno creado desde cero con `environment.yml` (2026-11-07).
- **Paridad del firmware en PC:** el codigo C de inferencia, compilado en el PC, coincide con la referencia Python.
- **Paridad en QEMU:** el binario real de ambas placas en el QEMU de Espressif. Error maximo contra Python de 1e-5 en FP32 y
  de 1e-7 en enteros. Rechaza modelo inexistente, observacion NaN y trama corrupta. En QEMU con el equipo cargado, alguna
  respuesta queda retenida hasta la siguiente peticion; la prueba la reintenta y la cuenta (`timeouts` en el JSON).
- **Determinismo:** con la misma semilla, el entorno es repetible bit a bit (se corrigio la fuerza obsoleta de `restoreState`).
- **Energia:** la cadena de B03 recupera una potencia conocida inyectada por una medidora simulada, con error menor a 3 %. El
  firmware de la medidora, ejecutado en QEMU, produce tramas que el host decodifica sin errores.

## 5. Resultados sin hardware

**[COMPLETAR con `results/report/tables.md` tras `benchmark.run_all --seeds 0 1 2`.]**

### 5.1 Entrenamiento

Revision con 4 de 6 corridas terminadas (ultimos 500 k pasos, evaluacion de 5 episodios cada 20 k):

| Corrida | Velocidad (m/s) | Caidas de 5 | Empieza a caminar |
|---|---|---|---|
| compact semilla 0 | 0.53 | 0.12 | 0.8 M |
| compact semilla 1 | 0.53 | 0.04 | 1.62 M |
| original semilla 0 | 0.28 | 0.48 | 1.68 M |
| original semilla 1 | 0.41 | 0.12 | antes de 1.16 M |

`best.pt` es el maximo de 150 evaluaciones de 5 episodios y sobreestima (compacto: 0.61 a 0.63 m/s frente a 0.53 de media). Las
cifras citables son las de B06, que reevalua con 50 episodios.

### 5.2 Cuantizacion

Hallazgos con la semilla 0, a confirmar con las tres:

- **INT16:** dentro del rango de calibracion el error de accion es despreciable (maximo 0.0027 en el original). La cola de error
  (P99.9 de 0.84 en el original) viene entera del ~1 % de observaciones de prueba fuera de ese rango. No es un fallo aritmetico:
  solo recortar esas entradas al rango, en FP32, ya cambia la accion hasta 1.96. El actor original es muy sensible fuera de lo
  que vio.
- **INT8 del original:** el error es alto tambien dentro del rango (P99.9 de 1.44 frente a 0.12 del compacto). El actor grande
  tolera peor la cuantizacion de 8 bits de sus activaciones.

### 5.3 B06 y B07

[COMPLETAR]

### 5.4 B02 y B05

[COMPLETAR]

## 6. Pendiente con hardware

Montaje y orden en `guia_conexion_hardware.md`. El codigo esta escrito y probado sin placa; falta:

- Paridad en silicio (`host.qemu_device --port`) y `psram_kb` cerca de 8192 en el S3.
- B01 y B04: latencia y jitter reales.
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
