# Pendientes para la proxima sesion

Corte: 2026-11-07, entrenamiento detenido a peticion del usuario. Para retomar, pedir: "lee documentation/PENDIENTES.md y sigue con el proyecto".

## 1. Primero: revisar el entrenamiento

**2026-11-07:** matriz relanzada en segundo plano desde PowerShell, agregando a `matrix.log`. Repite compact 1 desde cero; las
semillas 0 se saltan. Los bloques `NativeCommandError` del log son PowerShell envolviendo el stderr de pybullet: ruido, no fallo.

La matriz de 6 entrenamientos (2 arquitecturas, 3 semillas, 3 M pasos, unas 2 h cada uno a 430 pasos/s) quedo **detenida**, 2 de 6 hechos. Faltan unas 8 h.

| Entrenamiento | Estado al corte |
|---|---|
| compact semilla 0 | Terminado. Ultimos 500 k pasos: 0.53 m/s, 0.12 caidas de 5 por evaluacion |
| original semilla 0 | Terminado. Ultimos 500 k pasos: 0.28 m/s, 0.46 caidas de 5. Quieto hasta 1 M pasos, camina despues, irregular |
| compact 1 | Detenido a unos 380 k pasos. Se repite desde cero al relanzar |
| original 1, compact 2, original 2 | Sin empezar |

Comprobar:

    Get-Content results\training\matrix.log -Tail 3
    Get-ChildItem models\*\seed*\done.txt

**Para continuar:** `train.py` no reanuda desde `last.pt`. La corrida a medias se
pierde y empieza de cero; las que tienen `done.txt` se saltan. Relanzar desde el entorno `latiniot`, sin mas cambios:

    python -m reinforcement_learning.training.run_matrix --seeds 0 1 2 --steps 3000000

Redirigir con `>>`, no con `>`: el segundo borra `results/training/matrix.log`, que tiene el historial de las semillas 0.

**Decision por tomar:** con una semilla, el original rinde la mitad que el compacto. Se dejo seguir la matriz sin cambios: la semilla 1 dice si es variacion entre semillas o algo sistematico. Si se repite, investigar (por ejemplo tasa de aprendizaje), antes de la semilla 2. El compacto iba a
0.23 m/s a 800 k pasos. Solo intervenir si falla de verdad, y aplicar lo mismo a ambas arquitecturas.

## 2. Tareas sin hardware, en orden

1. [ ] Terminar la matriz de entrenamiento.
2. [ ] Correr `python -m benchmark.run_all --seeds 0 1 2`. Nunca se ha ejecutado como tal: el ensayo llamo a sus pasos por separado, sin
   firmware ni QEMU. Con el barrido de 60, 100 y 140 N de B07 tarda varias horas.
3. [ ] Revisar `results/report/tables.md` y las cuatro figuras.
4. [ ] Confirmar que 60, 100 y 140 N siguen separando resultados tambien en el actor original (se midio solo con el compacto).
5. [ ] Correr toda la suite junta: `python -m pytest -q`. Al corte solo se repitieron 37 pruebas afectadas. PyBullet llena la salida
   con `argv[0]=`: filtrar con `passed|failed`.
6. [ ] Escribir `documentation/informe_final.md`, con estas desviaciones declaradas: tobillo 0.3, ganancias PD, termino de energia
   (tau/tau_max)^2, sesgo inicial del actor, ruido de reset 0.02, criticos 256-256 en ambas arquitecturas, calendario 40 k / 160 k / 3 M,
   barrido de empujes en B07.
7. [ ] Probar `environment.yml` en un entorno limpio (lineas de `torch` y `ziglang` sin verificar).
8. [ ] Actualizar la memoria del proyecto.

`firmware/inference/models_generated.c` lleva hoy un actor original **aleatorio** (ensayo). `run_all` lo reemplaza; no grabarlo antes en una placa.

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
