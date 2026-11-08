# Formato numerico por runtime

Implementado en `reinforcement_learning/evaluation/quantization.py` (referencia) y `firmware/inference/policy.c` (firmware).
Una prueba exige igualdad bit a bit de los acumuladores enteros entre ambos.

| Elemento | FP32 | INT16 | INT8 |
|---|---|---|---|
| Pesos en flash | float32 | int16 por canal de salida, simetrico | int8 por canal de salida, simetrico |
| Sesgos | float32 | int64 a escala s_w * s_x | int64 a escala s_w * s_x |
| Activaciones | float32 | enteras hasta 32767 | enteras hasta 127 |
| Acumulador | float32 | int64 | int32 |
| Zero-point | no aplica | 0 | 0 |
| Entrada | float32 | float32 recibido, cuantizado en el dispositivo | igual |
| Reescalado entre capas | no aplica | entero: (acc * mult + redondeo) >> shift | igual |
| Salida | tanhf | acc * escala en float, luego tanhf | igual |

**Pesos y activaciones son cosas distintas aqui.** Los modelos INT16 e INT8 cuantizan ambos; no es cuantizacion solo de pesos.

**Escala de entrada por variable.** Las observaciones van de +/-1 a +/-20 sin normalizar. Con una escala unica, INT8 perderia
las variables pequenas. La escala s_in[i] se pliega en la primera capa, asi que el dispositivo solo multiplica por 1/s_in[i].

**Decisiones declaradas**
- Simetrico sin zero-point: tras ReLU se desperdicia la mitad negativa del rango, a cambio de un bucle interno sin correcciones.
- Calibracion con observaciones reales del simulador; el recorte (100, 99.99 o 99.9 por ciento) se elige por error en validacion.
- El acumulador INT16 necesita int64 porque 32767^2 * 256 no cabe en 32 bits. Eso encarece INT16 en un nucleo de 32 bits:
  no hay que asumir que INT16 cae entre FP32 e INT8 en latencia. Lo decide la medicion.

## Soporte por plataforma

| Aspecto | ESP32 clasico | ESP32-S3 |
|---|---|---|
| Nucleo | Xtensa LX6, 240 MHz | Xtensa LX7, 240 MHz |
| FPU de precision simple | Si | Si |
| Instrucciones vectoriales | No | Si (PIE), no usadas por este C portable |
| Runtime de este proyecto | C portable, mismo codigo | C portable, mismo codigo |

Comparacion justa de partida: el mismo C en ambos. Una variante con instrucciones vectoriales del S3 (ESP-DSP o ESP-DL) seria
otra fila de la matriz, nunca un reemplazo silencioso, porque cambia la aritmetica. ESP-DL no se integro ni se evaluo con
mediciones: queda pendiente, y sus capacidades por chip deben confirmarse en la documentacion de la version que se use.
