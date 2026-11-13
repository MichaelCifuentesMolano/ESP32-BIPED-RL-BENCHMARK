# Datos para el articulo: SAC cuantizado en ESP32 para un bipedo de 12 GdL

Paquete autocontenido para redactar el articulo. Fecha de corte: 2026-11-12. Todas las cifras salen de archivos del repositorio
(seccion 9). Reglas para quien redacte con este archivo:

- **Medido en placa** solo lo marcado como tal: ESP32 clasico real (seccion 5), ESP32-S3 real (seccion 5b) y energia (seccion 5c).
- **ESP32 virtual y QEMU no son mediciones de tiempo.** Sirven para desempeno funcional (velocidad, caidas), no para latencia.
- Energia (B03) medida en ambas placas con las desviaciones de la seccion 5c.4. No inventar cifras que no esten aqui.

## 1. Pregunta y diseno

Que pierde una politica SAC de locomocion bipeda al ejecutarse en un microcontrolador, en dos ejes:

- **Arquitectura del actor:** original 36-256-256-12 (la del articulo de referencia) frente a compacta 36-64-64-12 (propuesta).
  Criticos 256-256 en ambas (no se despliegan).
- **Formato numerico:** FP32, INT16 e INT8. Enteros simetricos, pesos por fila, activaciones calibradas con observaciones reales.

Banco hardware in the loop: el bipedo se simula en PyBullet en el PC; el actor corre en el ESP32, conectado por UART a
921 600 baudios a traves del puente USB de la placa (CH340 en el clasico, CH343 en el S3). Protocolo binario con CRC-16. Los 6 modelos van en una sola imagen
de firmware (ESP-IDF 5.5.1).

## 2. Montaje

| Elemento | Valor |
|---|---|
| Placa medida | ESP-WROOM-32, chip ESP32-D0WD-V3 rev. 3.1, 240 MHz, 2 nucleos, 4 MB flash, sin PSRAM, puente CH340 |
| SRAM | 387 KB total, 369 KB libre al arrancar, minimo libre 299.5 KB con los 6 modelos |
| Placa S3 medida | ESP32-S3 DevKit N16R8, chip rev. 2, 240 MHz, 2 nucleos, 16 MB flash, 8 MB PSRAM octal (reporta 8192 KB), puente CH343 |
| SRAM del S3 | 426 KB total, 378 KB libre al arrancar |
| Mismo firmware | Las dos placas corren la misma version (commit 5cf27ca) y los mismos 6 modelos de la semilla 0 |
| Simulacion | PyBullet 3.25, paso de 1 ms, control a 50 Hz (20 pasos por accion), 50 iteraciones de solver, 4 subpasos |
| Entrenamiento | SAC, 3 M pasos, 3 semillas por arquitectura, calendario de 3 fases (40 k / 160 k / 3 M), lote 256, buffer 1 M |
| PC | Intel Core 10a gen. (Family 6 Model 165), GPU RTX 3050, Python 3.11, PyTorch 2.11 |
| Episodio de evaluacion | 300 ciclos (6 s), ruido de reset 0.02 sembrado |

Desviaciones respecto al articulo de referencia (todas iguales para ambas arquitecturas): amortiguamiento de tobillo 0.3 (URDF)
en vez de 3.0; ganancias PD propias (kp 30, 150, 300, 200, 80, 30; kd 0.2, 6, 12, 8, 0.2, 0.1); termino de energia
(tau/tau_max)^2; sesgo inicial del actor hacia la postura de pie; ruido de reset 0.02; criticos 256-256; calendario 40 k / 160 k;
velocidad = desplazamiento / duracion; empujes de 60, 100 y 140 N en B07; placa S3 N16R8 en vez de N8R8. Detalle y motivos en
`documentation/informe_final.md`, seccion 3. Por estas desviaciones las velocidades no se comparan directamente con las del
articulo de referencia.

## 3. Entrenamiento

Ultimos 500 k pasos, evaluacion de 5 episodios cada 20 k. "Empieza a caminar": tercera evaluacion seguida con mas de 0.2 m/s.

| Actor | Semilla | Velocidad (m/s) | Caidas de 5 | Empieza a caminar |
|---|---|---|---|---|
| Compacto | 0 / 1 / 2 | 0.53 / 0.53 / 0.56 | 0.12 / 0.04 / 0.08 | 0.80 / 1.62 / 1.64 M |
| Original | 0 / 1 / 2 | 0.28 / 0.41 / 0.58 | 0.48 / 0.12 / 0.32 | 1.68 / 1.10 / 1.20 M |

Unas 2 h por corrida a 430 pasos/s. Figura: `results/report/fig_aprendizaje.png`.

## 4. Cuantizacion

Error de la accion (rango [-1, 1]) frente a FP32 sobre observaciones reales de prueba. Media +/- desviacion entre 3 semillas.

| Actor | Formato | Parametros (bytes) | MAE | Error P99.9 | Fuera de calibracion |
|---|---|---|---|---|---|
| Original | FP32 | 313 392 | ref. | ref. | |
| Original | INT16 | 162 592 | 0.00057 +/- 0.00018 | 0.64 +/- 0.27 | 0.82 % |
| Original | INT8 | 84 768 | 0.023 +/- 0.008 | 1.04 +/- 0.67 | 0.82 % |
| Compacto | FP32 | 29 232 | ref. | ref. | |
| Compacto | INT16 | 16 288 | 0.00026 +/- 0.00020 | 0.11 +/- 0.06 | 0.49 % |
| Compacto | INT8 | 9 120 | 0.012 +/- 0.002 | 0.48 +/- 0.44 | 0.49 % |

- La cola de error viene de las observaciones fuera del rango de calibracion, no de un fallo aritmetico.
- INT8: el original tiene el doble de error medio que el compacto en las 3 semillas.
- Este error no cambia la marcha (seccion 6). Figura: `results/report/fig_error_cuantizacion.png`.

## 5. Medido en el ESP32 clasico real

### 5.1 Paridad del firmware (2026-11-08)

Acciones de la placa frente a Python, 40 observaciones por modelo: error maximo 2.3e-6 en FP32 y 1.2e-7 en INT16 e INT8. 0
perdidas. Rechaza modelo inexistente, observacion NaN y trama corrupta. Reproducible bit a bit entre dos grabaciones (7 y 8 de
noviembre).

### 5.2 B01, latencia de inferencia (1 000 inferencias por modelo, PC sin carga)

Ida y vuelta = inferencia + envio y respuesta por UART/USB.

| Actor | Formato | Inferencia mediana (us) | P99 (us) | Ida y vuelta mediana (us) | P99 (us) | Dentro de 20 ms |
|---|---|---|---|---|---|---|
| Original | FP32 | 41 161 | 41 166 | 46 949 | 47 072 | 0 % |
| Original | INT16 | 25 552 | 25 588 | 30 954 | 31 174 | 0 % |
| Original | INT8 | 14 178 | 14 189 | 19 910 | 20 106 | 77.2 % |
| Compacto | FP32 | 1 396 | 1 398 | 6 948 | 7 139 | 100 % |
| Compacto | INT16 | 728 | 736 | 5 930 | 6 159 | 100 % |
| Compacto | INT8 | 544 | 549 | 5 934 | 6 190 | 100 % |

- La inferencia es casi determinista: desviacion de 1 a 21 us en el original.
- Unica excepcion: la primera inferencia de cada modelo compacto tarda 2 a 3 veces mas (4 031, 2 855 y 1 648 us), con la cache de
  flash fria. Las 999 siguientes estan dentro de +/- 1 % de la mediana.
- Speedup INT8 frente a FP32: 2.9x en el original y 2.6x en el compacto. Compacto frente a original en FP32: 29x.
- **El enlace cuesta de 5.2 a 5.8 ms** por ciclo (CH340 y USB). En el compacto es 4 a 10 veces la inferencia.
- **Causa de la lentitud del original:** los pesos son `static const` y viven en flash, leidos por una cache de 32 KB. El
  original FP32 (313 KB) ni siquiera cabe en la SRAM libre (299 KB). Decision abierta: copiar a SRAM los que quepan (seccion 8).

### 5.3 B04, jitter (100 000 inferencias por modelo)

2026-11-08, 15:03 a 18:18, PC sin carga. 600 000 inferencias en total: 0 tiempos de espera, 0 errores de CRC, 0 respuestas
fuera de orden.

| Actor | Formato | Inferencia mediana (us) | Desv. (us) | Min a max (us) | Ida y vuelta mediana (us) | P99 (us) | Max (us) | Dentro de 20 ms | Max. perdidos seguidos |
|---|---|---|---|---|---|---|---|---|---|
| Original | FP32 | 41 161 | 1.2 | 41 156 a 41 171 | 46 953 | 47 092 | 75 783 | 0 % | todos |
| Original | INT16 | 25 552 | 11.5 | 25 507 a 25 632 | 30 952 | 31 066 | 50 234 | 0 % | todos |
| Original | INT8 | 14 176 | 21.4 | 14 134 a 14 193 | 19 895 | 20 116 | 48 695 | 75.4 % | 4 |
| Compacto | FP32 | 1 397 | 8.4 | 1 395 a 4 031 | 6 949 | 7 146 | 22 199 | 99.999 % | 1 |
| Compacto | INT16 | 728 | 7.5 | 715 a 2 856 | 5 933 | 6 164 | 27 364 | 99.999 % | 1 |
| Compacto | INT8 | 544 | 4.4 | 535 a 1 649 | 5 928 | 6 163 | 37 430 | 99.999 % | 1 |

- **La inferencia en el ESP32 es practicamente determinista.** En el compacto, el maximo es siempre la primera inferencia
  (cache fria); sin ella, ninguna de las otras 99 999 se aleja mas de 5 % de la mediana. En el original FP32 las 100 000 caben
  en 15 us.
- **El jitter del ciclo viene del PC y del USB, no de la placa:** la desviacion de la ida y vuelta (75 a 139 us) es de 6 a 113
  veces la de la inferencia, y los maximos (22 a 76 ms) son eventos aislados del lado del PC.
- **Compacto:** 1 ciclo de 100 000 pasa de 20 ms en cada formato, siempre aislado.
- **Original INT8:** su ida y vuelta (19.9 ms) queda justo en el limite de 20 ms; cumple 75.4 % (77.2 % con 1 000 muestras en
  B01). Ningun formato del original es desplegable a 50 Hz en este montaje.
- B01 y B04 coinciden: las medianas difieren en 2 us o menos.

### 5.4 B05, ciclo HIL completo en la placa (semilla 0, 10 episodios por modelo)

El host espera la accion como maximo 15 ms (5 ms reservados al resto del ciclo de 20 ms). Si no llega, el ciclo cuenta como
perdido y se mantiene la accion anterior.

| Actor | Formato | Placa: velocidad (m/s) | Placa: caidas | Ciclos perdidos | Virtual: velocidad | Virtual: caidas |
|---|---|---|---|---|---|---|
| Original | FP32 | no camina | 10 de 10 | 100 % | 0.413 | 2 de 10 |
| Original | INT16 | no camina | 10 de 10 | 100 % | 0.386 | 2 de 10 |
| Original | INT8 | no camina | 10 de 10 | 100 % | 0.398 | 4 de 10 |
| Compacto | FP32 | 0.606 | 0 de 10 | 0 % | 0.599 | 0 de 10 |
| Compacto | INT16 | 0.618 | 0 de 10 | 0 % | 0.607 | 0 de 10 |
| Compacto | INT8 | 0.610 | 0 de 10 | 0 % | 0.608 | 0 de 10 |

- **Original:** ninguna accion llega a tiempo en ningun formato, ni siquiera INT8 (ida y vuelta de 19.9 ms frente a 15 ms
  disponibles). El robot queda con la postura inicial y cae en 1.6 s. La politica es buena (camina en el virtual); el
  despliegue es el que falla.
- **Compacto:** camina en la placa igual que en el virtual (diferencia de 0.01 m/s, dentro de la dispersion entre episodios).
  Ciclo completo: mediana de 10.0 a 11.0 ms, P99 de 12.7 a 13.9 ms. Mas de 20 ms solo 1 a 3 ciclos de 3 000, por el paso de
  PyBullet en el PC, no por la placa: inferencia + enlace nunca pasaron de 15 ms.
- El tiempo de PyBullet en el ciclo (unos 4.2 ms) no existiria en un robot real.

## 5b. Medido en el ESP32-S3 real

Mismo protocolo que en la seccion 5. Placa en COM8 por el conector COM/UART (CH343); el conector USB/OTG nativo no se usa.

### 5b.1 Paridad del firmware (2026-11-09)

40 observaciones por modelo: error maximo frente a Python 2.3e-6 en original FP32, 9.2e-7 en compacto FP32 y 1.2e-7 en los
cuatro modelos enteros. 0 perdidas. Rechaza modelo inexistente, observacion NaN y trama corrupta. La PSRAM inicia (8192 KB;
QEMU la reportaba en 0).

### 5b.2 B01, latencia de inferencia (1 000 inferencias por modelo, 2026-11-09)

| Actor | Formato | Inferencia mediana (us) | P99 (us) | Ida y vuelta mediana (us) | P99 (us) | Dentro de 20 ms |
|---|---|---|---|---|---|---|
| Original | FP32 | 20 709 | 20 711 | 24 914 | 25 060 | 0 % |
| Original | INT16 | 11 117 | 11 120 | 14 934 | 15 056 | 100 % |
| Original | INT8 | 5 889 | 5 892 | 9 943 | 10 046 | 100 % |
| Compacto | FP32 | 202 | 208 | 3 960 | 4 073 | 100 % |
| Compacto | INT16 | 410 | 411 | 3 958 | 4 494 | 100 % |
| Compacto | INT8 | 306 | 307 | 3 958 | 4 106 | 100 % |

- **En el S3 el compacto FP32 es el mas rapido de sus tres formatos** (202 us frente a 306 en INT8 y 410 en INT16). En el
  original los enteros si aceleran: INT8 es 3.5x mas rapido que FP32. La causa del caso compacto no se ha investigado; no
  atribuirla a nada concreto.
- Como en el clasico, el maximo del compacto es la primera inferencia (1 945, 1 156 y 659 us, cache fria).
- **El enlace cuesta de 3.5 a 4.2 ms** por ciclo (ida y vuelta menos inferencia), frente a 5.2 a 5.8 ms en el clasico (CH340).
- Compacto frente a original en FP32: 103x.

### 5b.3 B04, jitter (100 000 inferencias por modelo, 2026-11-11, 10:24 a 12:08)

600 000 inferencias: 0 tiempos de espera, 0 errores de CRC, 0 respuestas fuera de orden.

| Actor | Formato | Inferencia mediana (us) | Desv. (us) | Min a max (us) | Ida y vuelta mediana (us) | P99 (us) | Max (us) | Dentro de 20 ms | Max. perdidos seguidos |
|---|---|---|---|---|---|---|---|---|---|
| Original | FP32 | 20 710 | 1.3 | 20 704 a 20 739 | 24 904 | 25 067 | 55 141 | 0 % | todos |
| Original | INT16 | 11 117 | 1.7 | 11 108 a 11 122 | 14 919 | 15 092 | 45 087 | 99.997 % | 1 |
| Original | INT8 | 5 889 | 1.4 | 5 882 a 5 900 | 9 931 | 10 082 | 40 351 | 99.997 % | 1 |
| Compacto | FP32 | 202 | 6.1 | 200 a 1 945 | 3 955 | 4 107 | 30 425 | 99.998 % | 1 |
| Compacto | INT16 | 410 | 2.4 | 405 a 1 156 | 3 960 | 4 778 | 31 758 | 99.998 % | 1 |
| Compacto | INT8 | 307 | 1.3 | 301 a 660 | 3 957 | 4 132 | 32 787 | 99.998 % | 1 |

- Inferencia igual de determinista que en el clasico: en el original las 100 000 caben en 35 us o menos.
- Los maximos de ida y vuelta (30 a 55 ms) son eventos aislados del PC y del USB, como en el clasico.
- B01 y B04 coinciden: las medianas difieren en 1 us o menos.

### 5b.4 B05, ciclo HIL completo en el S3 (semilla 0, 10 episodios, plazo de 15 ms, 2026-11-11)

| Actor | Formato | Velocidad (m/s) | Caidas | Ciclos perdidos | Max. perdidos seguidos | Ciclo mediana / P99 (ms) |
|---|---|---|---|---|---|---|
| Original | FP32 | no camina | 10 de 10 | 100 % | todos | 21.3 / 27.9 |
| Original | INT16 | no camina (cae a los 1.8 s) | 10 de 10 | 30.3 % | 7 | 19.0 / 24.6 |
| Original | INT8 | 0.413 | 1 de 10 | 0 % | 0 | 13.7 / 17.8 |
| Compacto | FP32 | 0.605 | 0 de 10 | 0 % | 0 | 8.1 / 11.2 |
| Compacto | INT16 | 0.618 | 0 de 10 | 0 % | 0 | 8.3 / 10.7 |
| Compacto | INT8 | 0.610 | 0 de 10 | 0 % | 0 | 8.2 / 10.3 |

- **En el S3 el original solo es desplegable en INT8** (en el clasico, en ningun formato). Camina a 0.41 m/s con 1 caida de 10,
  la misma velocidad que en el virtual (0.398, seccion 5.4).
- **Original INT16:** 11.1 ms de inferencia mas unos 3.7 ms de enlace rozan los 15 ms; pierde el 30 % de los ciclos y cae.
  Aqui el plazo de 15 ms decide el resultado (seccion 8).
- **Compacto:** igual que en el clasico y en el virtual (diferencia de 0.01 m/s o menos). Inferencia mas enlace nunca pasa de
  6.5 ms. Un ciclo de 9 000 pasa de 20 ms, por el paso de PyBullet en el PC.
- Enlace mediano en B05: 3.7 a 3.9 ms. PyBullet en el PC: unos 4.1 ms por ciclo.

### 5b.5 Verificacion independiente con analizador logico (2026-11-11)

El firmware sube GPIO4 durante la inferencia y GPIO5 desde que recibe la trama hasta que envia la respuesta. Analizador de
8 canales (fx2lafw, sigrok) a **12 MHz** (83 ns por muestra; a 24 MHz el USB del PC corta la captura, tambien en un puerto
USB 3.0). Capturas durante B01, en el tramo FP32.

| Actor | GPIO4 mediana (us) | B01 mediana, temporizador interno (us) | GPIO5 mediana (us) | GPIO5 menos GPIO4 (us) |
|---|---|---|---|---|
| Original FP32 | 20 711 (120 pulsos) | 20 710 | 20 778 | unos 66 |
| Compacto FP32 | 203 (166 pulsos) | 202 | 254 | unos 51 |

- **El temporizador interno del firmware coincide con la medicion externa a 1 us.** El maximo del compacto (1 946 us, primera
  inferencia) tambien coincide con el de B01 (1 945 us).
- GPIO4 cae siempre dentro de GPIO5. GPIO5 menos GPIO4 es lo que tarda el firmware en recibir, validar el CRC y responder.
- UART a 921 600 8N1 decodificado: 0 errores de trama (164 bytes por trama del PC, 66 por respuesta).
- Solo se verifico FP32 y solo en el S3.

### 5b.6 Clasico frente a S3 (mismo firmware y modelos)

| Actor | Formato | Inferencia clasico (us) | Inferencia S3 (us) | S3 mas rapido | Ida y vuelta clasico (us) | Ida y vuelta S3 (us) |
|---|---|---|---|---|---|---|
| Original | FP32 | 41 161 | 20 709 | 2.0x | 46 949 | 24 914 |
| Original | INT16 | 25 552 | 11 117 | 2.3x | 30 954 | 14 934 |
| Original | INT8 | 14 178 | 5 889 | 2.4x | 19 910 | 9 943 |
| Compacto | FP32 | 1 396 | 202 | 6.9x | 6 948 | 3 960 |
| Compacto | INT16 | 728 | 410 | 1.8x | 5 930 | 3 958 |
| Compacto | INT8 | 544 | 306 | 1.8x | 5 934 | 3 958 |

Medianas de B01 (1 000 inferencias). Las dos placas a 240 MHz. La ida y vuelta mezcla placa y puente USB (CH340 frente a CH343):
la diferencia de enlace no es atribuible solo al chip.

## 5c. Energia, B03, medida en placa (2026-11-12)

### 5c.1 Montaje real

- Sensor: modulo INA226 (direccion 0x44), shunt de 0.1 ohm en el lado alto, conversion de 140 us sin promediado, lectura de
  shunt y bus en cada muestra. La conversion a unidades se hace en el PC desde los registros crudos.
- La placa que no se mide lee el INA226 y envia las muestras por su USB; luego se invierten. Clasico medido: medidora el S3
  (1777 muestras/s). S3 medido: medidora el clasico (1417 muestras/s). La frecuencia la limita la lectura I2C, no el INA226.
- La placa medida no tiene USB conectado. El protocolo va por un FT232RL (latency timer 1 ms) al UART0 de la placa. Se comprobo
  que el puente USB propio de la placa (CH340 o CH343) no estorba: B01 corto por el FT232RL igual al de USB en ambas placas.
- Alimentacion: la placa medida recibe 3.45 V en su pin 3V3 desde el regulador de 3.3 V de la medidora, a traves del shunt.
- Protocolo: 60 s de reposo, un tramo de 60 s por modelo pidiendo inferencias a 50 Hz, y 60 s de reposo. Se recorta 1 s en cada
  borde. Reposo = promedio de los dos reposos. Potencia atribuible = potencia del tramo menos reposo. Energia por inferencia
  atribuible = potencia atribuible / inferencias por segundo reales del tramo. 0 errores de lectura y 0 inferencias perdidas en
  las dos corridas. Semilla 0, firmware del commit 5cf27ca (el mismo de las secciones 5 y 5b).
- Reposo = CPU encendida esperando una trama por UART, sin modos de bajo consumo ni WiFi.

### 5c.2 Resultados

| | Clasico | S3 |
|---|---|---|
| Reposo | 145.6 mW (42.2 mA a 3.449 V) | 127.0 mW (36.8 mA a 3.446 V) |
| Deriva entre reposos | 0.75 mW | 0.95 mW |

Energia atribuible por inferencia (mJ) e inferencias por segundo alcanzadas:

| Actor | Formato | Clasico (mJ) | Clasico (inf/s) | S3 (mJ) | S3 (inf/s) |
|---|---|---|---|---|---|
| Original | FP32 | 1.21 | 21.7 | 1.42 | 40.0 |
| Original | INT16 | 1.00 | 33.3 | 0.92 | 50.0 |
| Original | INT8 | 0.61 | 50.0 | 0.56 | 50.0 |
| Compacto | FP32 | 0.090 | 50.0 | 0.055 | 50.0 |
| Compacto | INT16 | 0.085 | 50.0 | 0.066 | 50.0 |
| Compacto | INT8 | 0.069 | 50.0 | 0.058 | 50.0 |

Potencia de placa en cada tramo (mW; error estandar por bloques de 1 s entre 0.01 y 0.8 mW):

| Actor | Formato | Clasico | S3 |
|---|---|---|---|
| Original | FP32 / INT16 / INT8 | 171.9 / 178.8 / 175.9 | 183.8 / 173.0 / 154.9 |
| Compacto | FP32 / INT16 / INT8 | 150.0 / 149.8 / 149.0 | 129.8 / 130.3 / 129.9 |

Cuando no se alcanzan 50 inf/s, la inferencia mas el enlace superan los 20 ms y el host pide la siguiente en cuanto llega la
respuesta: esos tramos no son comparables en potencia, si en energia por inferencia.

### 5c.3 Lectura

- **Original:** INT8 gasta la mitad de energia por inferencia que FP32 en ambas placas (0.61 frente a 1.21 mJ en el clasico;
  0.56 frente a 1.42 mJ en el S3). El ahorro viene del menor tiempo de computo.
- **El S3 calcula mas rapido pero con mas potencia:** potencia extra durante el computo, estimada como atribuible / (inf/s x
  tiempo B01), unos 29 a 43 mW en el clasico y 69 a 94 mW en el S3. Por eso en original FP32 el S3 gasta mas por inferencia
  (1.42 frente a 1.21 mJ) pese a ser 2 veces mas rapido; en INT16 e INT8 gasta algo menos. Esta potencia es una estimacion
  derivada, no una medicion directa.
- **Compacto:** 0.055 a 0.090 mJ por inferencia, entre 7 y 26 veces menos que el original segun formato y placa. Las diferencias
  entre sus formatos (0.7 a 1.6 mW atribuibles) son del orden de la deriva (0.75 a 0.95 mW): **no se puede afirmar que un
  formato gaste menos que otro en el compacto.**
- **A 50 Hz el reposo domina:** con el compacto, la inferencia es el 2 al 3 % de la energia de la placa. Por ciclo de control
  de 20 ms la placa gasta unos 3.0 mJ (clasico) y 2.6 mJ (S3); el S3 sale mas barato por su menor consumo en reposo.
- "Atribuible" incluye recibir la observacion y responder por UART, no solo la red.

### 5c.4 Desviaciones que hay que declarar

1. Alimentacion por el pin 3V3 y no por 5V: el pin 5V del S3 es solo entrada ("5Vin") y no habia fuente regulada. Se mide el
   ESP32 con sus perifericos de placa, sin su regulador de 5 V a 3.3 V. La potencia absoluta es menor que la de una placa
   alimentada por 5 V; la atribuible casi no cambia.
2. Shunt nominal de 0.1 ohm sin calibrar (no habia multimetro). Corrientes, potencias y energias escalan como 0.1 / R real;
   la tolerancia tipica de estos shunts es 1 %. Los cocientes entre modelos no dependen del shunt.
3. Una corrida de 60 s por modelo y placa; la incertidumbre dominante es la deriva entre reposos, no el error estandar.
4. El modulo INA226 necesito un puente de VBUS a VIN- para leer la tension de bus.

## 6. Desempeno con el ESP32 virtual (3 semillas, 50 episodios por modelo y semilla)

El ESP32 virtual ejecuta la aritmetica exacta del firmware (validada contra la placa en 5.1), con inferencia instantanea: mide
lo que la politica cuantizada sabe hacer, no si llega a tiempo.

B06, sin empujes (150 episodios por fila):

| Actor | Formato | Velocidad (m/s) | Caidas |
|---|---|---|---|
| Original | FP32 / INT16 / INT8 | 0.527 / 0.527 / 0.523 (+/- 0.10 entre semillas) | 10 / 5 / 12 de 150 |
| Compacto | FP32 / INT16 / INT8 | 0.614 / 0.615 / 0.613 (+/- 0.01 entre semillas) | 0 / 2 / 2 de 150 |

B07, empuje de 0.1 s en el ciclo 100 (2 s), alternando sentido y eje (frontal o lateral) entre episodios; episodios con caida de
150:

| Actor | Formato | 60 N | 100 N | 140 N |
|---|---|---|---|---|
| Original | FP32 / INT16 / INT8 | 24 / 25 / 22 | 51 / 63 / 60 | 104 / 111 / 105 |
| Compacto | FP32 / INT16 / INT8 | 9 / 15 / 6 | 59 / 45 / 46 | 116 / 108 / 105 |

- **Cuantizar no cambia la marcha:** la velocidad media cambia menos de 0.005 m/s entre formatos.
- **B07 no distingue formatos:** de 18 comparaciones por pares, la mayor da z = 2.04; con Bonferroni el umbral es 2.99.
- **Las caidas suben con la fuerza** en los 6 modelos y las 3 semillas.
- **El compacto es mas rapido y mas estable entre semillas.** El original depende mucho de la semilla (0.41 a 0.65 m/s).
- B06 evalua `best.pt` (mejor evaluacion del entrenamiento); por eso sus velocidades superan las de la seccion 3.
- Figuras: `results/report/fig_velocidad.png`, `results/report/fig_robustez.png`.

## 7. Memoria (B02)

Imagen con los 6 modelos: 642 KB de datos en flash en el esp32 (parametros: 615 KB) y 644 KB en el S3. DRAM estatica: 14.7 KB
en el esp32. Codigo en flash: 74 KB (esp32) y 89 KB (S3).

## 8. Lo que el articulo no puede afirmar todavia

- **Energia (B03):** medida (seccion 5c) con shunt sin calibrar y alimentacion por 3V3; no hay potencia de la placa completa
  alimentada por 5 V ni diferencias significativas entre formatos del compacto.
- **ESP32-S3:** medido en placa (secciones 5b y 5c), salvo B06 y B07. Los pesos tampoco se movieron a PSRAM o SRAM.
- **Analizador logico:** solo FP32 y solo en el S3; el clasico no tiene verificacion externa del temporizador.
- **B06 y B07 en placa:** solo con el virtual. B05 en placa (seccion 5.4) respalda que el compacto se comporta igual.
- **Plazo de 15 ms:** es una decision del banco, no un requisito del robot. En el clasico, con 20 ms el original INT8 entraria en el 75 % de
  los ciclos (B04), con hasta 4 perdidos seguidos. En el S3 decide el resultado del original INT16 (30 % perdidos con 15 ms; con 20 ms el 99.997 % llegaria a tiempo, B04).
  Decision pendiente del autor (ver "Decisiones abiertas" en `documentation/PENDIENTES.md`).
- **D7:** los pesos estan en flash (despliegue estandar). Copiar a SRAM los que quepan podria acelerar el original INT16 e INT8;
  no se ha probado.
- **Rodilla (D1):** el URDF se uso sin cambios; si el robot ARON real flexiona distinto, hay que reentrenar.
- Una sola placa fisica de cada tipo: no hay variacion entre ejemplares.

## 9. Procedencia

| Dato | Archivo |
|---|---|
| Entrenamiento | `models/{compact,original}/seed{0,1,2}/train_log.csv` y `run.json` |
| Cuantizacion | `results/quantization/seed{0,1,2}.json` |
| B06, B07, B02, B05 virtual | `results/report/tables.md` (generado por `benchmark.run_all`) |
| Paridad en placa | `results/firmware/hw_parity_esp32.json`, `results/firmware/hw_parity_esp32s3.json` |
| B01, B04, B05 en placa | `results/B01/`, `results/B04/`, `results/B05/` (`result.json` y `raw.csv`; campo `platform` = esp32 o esp32s3) |
| Registro de las sesiones de placa | `results/hw_2026-11-08.log` (clasico), `results/hw_2026-11-09_s3.log` (S3) |
| Energia B03 | `results/B03/B03_55b404bd/` (clasico), `results/B03/B03_eb26284f/` (S3): `result.json` y `raw.csv` (t, v, i por tramo) |
| Analizador logico | `results/firmware/gpio_s3/` (capturas `.sr`, `pulsos_*.json`, README), `analysis/sr_pulses.py` |
| Metodo completo y desviaciones | `documentation/informe_final.md` |

Repositorio git local. Clasico: commits del 2026-11-08 (adff2a6). S3: 0618942 (paridad, B01, B04, B05) y f25667b (analizador). B03: 06eacaa (clasico) y el commit siguiente (S3).
Las corridas de B01 del S3 del 2026-11-11 (400 y 5 000 muestras) solo acompanan a las capturas; las tablas usan las del 9 de
noviembre (1 000 muestras).
