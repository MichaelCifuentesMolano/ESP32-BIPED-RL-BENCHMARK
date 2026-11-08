# Resultados generados
Tiempos de dispositivo: sin placa no hay mediciones; B05 a B07 usan el ESP32 virtual.

## Cuantizacion (observaciones reales de prueba)
| Arquitectura | Formato | Parametros (bytes) | MAE | RMSE | Error P99.9 | Error max | Fuera de calibracion (%) |
|---|---|---|---|---|---|---|---|
| Original 256-256 | FP32 | 313392 | referencia | referencia | referencia | referencia |  |
| Original 256-256 | INT16 | 162592 | 0.00057 +/- 0.00018 | 0.01758 +/- 0.00524 | 0.64005 +/- 0.26540 | 1.66759 +/- 0.11231 | 0.82 |
| Original 256-256 | INT8 | 84768 | 0.02319 +/- 0.00849 | 0.05075 +/- 0.02765 | 1.04387 +/- 0.66720 | 1.70301 +/- 0.20496 | 0.82 |
| Compacto 64-64 | FP32 | 29232 | referencia | referencia | referencia | referencia |  |
| Compacto 64-64 | INT16 | 16288 | 0.00026 +/- 0.00020 | 0.00922 +/- 0.00901 | 0.10994 +/- 0.05609 | 0.99789 +/- 0.69240 | 0.49 |
| Compacto 64-64 | INT8 | 9120 | 0.01223 +/- 0.00182 | 0.02535 +/- 0.01112 | 0.47566 +/- 0.43890 | 1.06153 +/- 0.66157 | 0.49 |

## B06 Locomocion (media entre semillas)
| Arquitectura | Formato | Semillas | Velocidad (m/s) | Distancia (m) | Caidas | Pitch RMS (rad) | Retorno |
|---|---|---|---|---|---|---|---|
| Original 256-256 | FP32 | 3 | 0.527 +/- 0.098 | 3.06 +/- 0.71 | 10 de 150 | 0.216 +/- 0.106 | 1190 +/- 132 |
| Original 256-256 | INT16 | 3 | 0.527 +/- 0.102 | 3.11 +/- 0.67 | 5 de 150 | 0.212 +/- 0.102 | 1213 +/- 103 |
| Original 256-256 | INT8 | 3 | 0.523 +/- 0.101 | 3.06 +/- 0.69 | 12 de 150 | 0.218 +/- 0.108 | 1196 +/- 119 |
| Compacto 64-64 | FP32 | 3 | 0.614 +/- 0.011 | 3.68 +/- 0.06 | 0 de 150 | 0.126 +/- 0.013 | 1325 +/- 10 |
| Compacto 64-64 | INT16 | 3 | 0.615 +/- 0.009 | 3.66 +/- 0.08 | 2 de 150 | 0.129 +/- 0.011 | 1312 +/- 27 |
| Compacto 64-64 | INT8 | 3 | 0.613 +/- 0.011 | 3.67 +/- 0.07 | 2 de 150 | 0.127 +/- 0.012 | 1320 +/- 17 |

## B07 Empuje de 60 N (media entre semillas)
| Arquitectura | Formato | Semillas | Velocidad (m/s) | Distancia (m) | Caidas | Pitch RMS (rad) | Retorno |
|---|---|---|---|---|---|---|---|
| Original 256-256 | FP32 | 3 | 0.520 +/- 0.096 | 2.91 +/- 0.73 | 24 de 150 | 0.223 +/- 0.100 | 1130 +/- 151 |
| Original 256-256 | INT16 | 3 | 0.524 +/- 0.099 | 2.90 +/- 0.70 | 25 de 150 | 0.222 +/- 0.100 | 1128 +/- 140 |
| Original 256-256 | INT8 | 3 | 0.528 +/- 0.094 | 3.01 +/- 0.66 | 22 de 150 | 0.225 +/- 0.104 | 1168 +/- 114 |
| Compacto 64-64 | FP32 | 3 | 0.594 +/- 0.003 | 3.46 +/- 0.12 | 9 de 150 | 0.139 +/- 0.009 | 1270 +/- 44 |
| Compacto 64-64 | INT16 | 3 | 0.592 +/- 0.001 | 3.38 +/- 0.07 | 15 de 150 | 0.142 +/- 0.007 | 1237 +/- 35 |
| Compacto 64-64 | INT8 | 3 | 0.597 +/- 0.017 | 3.54 +/- 0.12 | 6 de 150 | 0.135 +/- 0.010 | 1294 +/- 31 |

## B07 Empuje de 100 N (media entre semillas)
| Arquitectura | Formato | Semillas | Velocidad (m/s) | Distancia (m) | Caidas | Pitch RMS (rad) | Retorno |
|---|---|---|---|---|---|---|---|
| Original 256-256 | FP32 | 3 | 0.502 +/- 0.076 | 2.50 +/- 0.74 | 51 de 150 | 0.240 +/- 0.101 | 971 +/- 204 |
| Original 256-256 | INT16 | 3 | 0.506 +/- 0.093 | 2.37 +/- 0.63 | 63 de 150 | 0.248 +/- 0.089 | 919 +/- 142 |
| Original 256-256 | INT8 | 3 | 0.508 +/- 0.091 | 2.39 +/- 0.59 | 60 de 150 | 0.242 +/- 0.086 | 936 +/- 126 |
| Compacto 64-64 | FP32 | 3 | 0.555 +/- 0.011 | 2.64 +/- 0.24 | 59 de 150 | 0.178 +/- 0.013 | 986 +/- 87 |
| Compacto 64-64 | INT16 | 3 | 0.579 +/- 0.007 | 2.91 +/- 0.06 | 45 de 150 | 0.166 +/- 0.019 | 1068 +/- 16 |
| Compacto 64-64 | INT8 | 3 | 0.579 +/- 0.009 | 2.89 +/- 0.03 | 46 de 150 | 0.168 +/- 0.019 | 1070 +/- 26 |

## B07 Empuje de 140 N (media entre semillas)
| Arquitectura | Formato | Semillas | Velocidad (m/s) | Distancia (m) | Caidas | Pitch RMS (rad) | Retorno |
|---|---|---|---|---|---|---|---|
| Original 256-256 | FP32 | 3 | 0.479 +/- 0.063 | 1.85 +/- 0.51 | 104 de 150 | 0.267 +/- 0.081 | 701 +/- 130 |
| Original 256-256 | INT16 | 3 | 0.453 +/- 0.080 | 1.66 +/- 0.44 | 111 de 150 | 0.265 +/- 0.078 | 650 +/- 108 |
| Original 256-256 | INT8 | 3 | 0.476 +/- 0.081 | 1.78 +/- 0.41 | 105 de 150 | 0.257 +/- 0.079 | 685 +/- 86 |
| Compacto 64-64 | FP32 | 3 | 0.519 +/- 0.011 | 1.78 +/- 0.22 | 116 de 150 | 0.215 +/- 0.018 | 658 +/- 93 |
| Compacto 64-64 | INT16 | 3 | 0.536 +/- 0.010 | 1.93 +/- 0.11 | 108 de 150 | 0.199 +/- 0.019 | 703 +/- 46 |
| Compacto 64-64 | INT8 | 3 | 0.545 +/- 0.008 | 1.99 +/- 0.12 | 105 de 150 | 0.193 +/- 0.016 | 724 +/- 57 |

## B02 Memoria estatica del firmware con los 6 modelos (bytes)
| Objetivo | DIRAM | DRAM | Flash Code | Flash Data | IRAM | RTC FAST | RTC SLOW |
|---|---|---|---|---|---|---|---|
| esp32 |  | 14696 | 73664 | 642304 | 51707 |  | 56 |
| esp32s3 | 58551 |  | 88516 | 643748 | 16384 | 24 | 32 |

## B05 Ciclo HIL con ESP32 virtual
El tiempo del host es real; dispositivo y enlace estan simulados.

| Arquitectura | Formato | Host mediana (us) | Host P99 (us) | Ciclo mediana (us) | Ciclo P99 (us) | Ciclos <= 20 ms (%) |
|---|---|---|---|---|---|---|
| Original 256-256 | FP32 | 3640 | 5732 | 6945 | 9064 | 100.0 |
| Original 256-256 | INT16 | 3659 | 5786 | 6967 | 9115 | 100.0 |
| Original 256-256 | INT8 | 3667 | 5594 | 6968 | 8890 | 100.0 |
| Compacto 64-64 | FP32 | 4002 | 6033 | 7304 | 9385 | 99.9 |
| Compacto 64-64 | INT16 | 3971 | 5691 | 7276 | 8989 | 100.0 |
| Compacto 64-64 | INT8 | 3982 | 5720 | 7283 | 9020 | 100.0 |
