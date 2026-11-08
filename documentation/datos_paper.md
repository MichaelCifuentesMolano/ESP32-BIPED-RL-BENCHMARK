# Datos para el articulo: SAC cuantizado en ESP32 para un bipedo de 12 GdL

Paquete autocontenido para redactar el articulo. Fecha de corte: 2026-11-08. Todas las cifras salen de archivos del repositorio
(seccion 9). Reglas para quien redacte con este archivo:

- **Medido en placa** solo lo marcado como tal: ESP32 clasico real. El ESP32-S3 no se ha medido.
- **ESP32 virtual y QEMU no son mediciones de tiempo.** Sirven para desempeno funcional (velocidad, caidas), no para latencia.
- No hay datos de energia (B03) todavia. No inventar cifras que no esten aqui.

## 1. Pregunta y diseno

Que pierde una politica SAC de locomocion bipeda al ejecutarse en un microcontrolador, en dos ejes:

- **Arquitectura del actor:** original 36-256-256-12 (la del articulo de referencia) frente a compacta 36-64-64-12 (propuesta).
  Criticos 256-256 en ambas (no se despliegan).
- **Formato numerico:** FP32, INT16 e INT8. Enteros simetricos, pesos por fila, activaciones calibradas con observaciones reales.

Banco hardware in the loop: el bipedo se simula en PyBullet en el PC; el actor corre en el ESP32, conectado por UART a
921 600 baudios a traves del puente USB de la placa (CH340). Protocolo binario con CRC-16. Los 6 modelos van en una sola imagen
de firmware (ESP-IDF 5.5.1).

## 2. Montaje

| Elemento | Valor |
|---|---|
| Placa medida | ESP-WROOM-32, chip ESP32-D0WD-V3 rev. 3.1, 240 MHz, 2 nucleos, 4 MB flash, sin PSRAM, puente CH340 |
| SRAM | 387 KB total, 369 KB libre al arrancar, minimo libre 299.5 KB con los 6 modelos |
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

- **Energia (B03):** sin datos. El codigo esta listo; falta montar el INA226.
- **ESP32-S3:** sin medicion. Solo compila y pasa la paridad en QEMU (que reporta 0 KB de PSRAM; hay que comprobarla en placa).
- **B06 y B07 en placa:** solo con el virtual. B05 en placa (seccion 5.4) respalda que el compacto se comporta igual.
- **Plazo de 15 ms:** es una decision del banco, no un requisito del robot. Con 20 ms el original INT8 entraria en el 75 % de
  los ciclos (B04), con hasta 4 perdidos seguidos. Decision pendiente del autor (ver "Decisiones abiertas" en `documentation/PENDIENTES.md`).
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
| Paridad en placa | `results/firmware/hw_parity_esp32.json` |
| B01, B04, B05 en placa | `results/B01/`, `results/B04/`, `results/B05/` (`result.json` y `raw.csv`; `platform` = esp32) |
| Registro de la sesion de placa | `results/hw_2026-11-08.log` |
| Metodo completo y desviaciones | `documentation/informe_final.md` |

Repositorio git local; los resultados de esta fecha estan en los commits del 2026-11-08.
