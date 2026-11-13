# Guia de conexion de hardware

Paso a paso para montar y medir B01, B03, B04 y B05 a B07 cuando lleguen las placas. Amplia `guia_hardware.md`, que queda como
resumen de comandos.

Regla de esta guia: lo marcado **[CONFIRMAR]** depende del ejemplar fisico y se verifica con la placa en la mano antes de conectar.
Los pines de UART0 y de arranque son del chip (hoja de datos de Espressif) y no cambian entre fabricantes; la serigrafia y el puente
USB si cambian.

## 1. Materiales

| Elemento | Modelo | Uso | Datos por confirmar al llegar |
|---|---|---|---|
| Placa A | ESP-WROOM-32, USB-C | Objetivo ESP32 clasico | Confirmado 2026-11-07: blindaje ESP-WROOM-32, chip ESP32-D0WD-V3 rev. v3.1, puente CH340 (COM5 en este PC). **[CONFIRMAR]** 30 o 38 pines |
| Placa B | ESP32-S3 DevKit N16R8 | Objetivo ESP32-S3 | **[CONFIRMAR]** chip USB, cual conector dice COM/UART y cual USB/OTG |
| ESP32 clasico propio | El que ya tienes | Reserva o medidora | **[CONFIRMAR]** modulo |
| INA226 | Modulo I2C 0-36 V | B03, lado alto | **[CONFIRMAR]** shunt (la resistencia grande suele decir R100 = 0.1 ohm), direccion I2C (puentes A0 y A1) |
| FT232RL | Adaptador mini USB a TTL 3.3/5 V | UART sin el USB de la placa | **[CONFIRMAR]** puente de tension en **3.3 V** |
| Analizador logico | 8 canales, 24 MHz | GPIO4, GPIO5 y lineas UART | Software: PulseView (sigrok), controlador `fx2lafw` |
| Fuente regulada | La tuya | Alimentacion en B03 | **[CONFIRMAR]** rango de tension y limite de corriente |
| Multimetro | El tuyo | Calibrar shunt, revisar tensiones | Modelo y exactitud, para la incertidumbre |
| Cables | Dupont macho/hembra, USB-C de datos (no solo carga), mini USB | | Al menos 15 Dupont |

Sobre la placa S3: es N16R8 (16 MB flash). El articulo usa N8R8. La PSRAM es la misma (8 MB octal) y el firmware ya esta
configurado a 16 MB. Se declara como desviacion sin efecto en la inferencia.

Sobre la placa A: el modulo ESP-WROOM-32 sin sufijo puede traer un chip de revision antigua. `read_device_info` registra la revision;
se reporta tal cual en el articulo.

## 2. Pines que usa el firmware

| Senal | ESP32 (placa A) | ESP32-S3 (placa B) | Notas |
|---|---|---|---|
| UART0 TX (sale del ESP) | GPIO1 (TX0, TXD) | GPIO43 (TX) | Protocolo a 921600 baudios, 8N1 |
| UART0 RX (entra al ESP) | GPIO3 (RX0, RXD) | GPIO44 (RX) | |
| Inferencia | GPIO4 | GPIO4 | Alto durante `policy_run` |
| Trama | GPIO5 | GPIO5 | Alto desde trama recibida hasta respuesta enviada |
| GND | GND | GND | Comun con todo |

Pines que no se tocan:

- **ESP32 clasico:** GPIO 6 a 11 (flash interna del modulo). GPIO 0, 2, 12 y 15 son de arranque. **GPIO5 tambien es de arranque**:
  el analizador es una entrada de alta impedancia y no lo afecta, pero no conectarle resistencias ni otros circuitos.
- **ESP32-S3 N16R8:** GPIO 26 a 37 (flash y PSRAM octal). GPIO 0, 3, 45 y 46 son de arranque. GPIO19 y 20 son el USB nativo.
- **[CONFIRMAR]** en la serigrafia de cada placa que GPIO4 y GPIO5 salen a un pin del conector y que nada de la placa (LED, boton)
  esta conectado a ellos.
- **[CONFIRMAR]** en la placa que haga de medidora que salen al conector GPIO21 y GPIO22 (clasico) o GPIO8 y GPIO9 (S3), los
  pines I2C que usa `firmware/meter_app`.

## 3. Montajes

Hay tres montajes. Cada medicion indica cual usar.

### Montaje 1: solo USB (B01, B04, B06, B07, y grabar)

    PC --USB-C de datos--> Placa (conector COM/UART en el S3)

La placa se alimenta y se comunica por su propio puente USB. Es el mas simple y el que se usa para grabar.

### Montaje 2: USB con analizador (B05, y opcional en B01 y B04)

    PC --USB--> Placa
    PC --USB--> Analizador
                 CH1 (D0) ---- GPIO4
                 CH2 (D1) ---- GPIO5
                 CH3 (D2) ---- RX del ESP (GPIO3 / GPIO44)   opcional: decodifica la trama del host
                 CH4 (D3) ---- TX del ESP (GPIO1 / GPIO43)   opcional: decodifica la respuesta

El analizador numera los canales de CH1 a CH8 en su serigrafia; PulseView y sigrok-cli los llaman D0 a D7 (CH1 = D0).
                 GND ---- GND de la placa

CH3 y CH4 permiten ver en PulseView cuando llega el ultimo byte de la trama y cuando sale la respuesta, y separar lo que tarda
el ESP32 de lo que tarda Windows. A 24 MHz cada muestra dura unos 42 ns. Si PulseView reporta muestras perdidas con 4 canales,
bajar a 12 MHz (83 ns) y anotarlo.

### Montaje 3: energia con INA226 y FT232RL (B03)

La placa bajo prueba **no** se conecta por USB: el puente USB tambien consume y el PC la alimentaria por otro camino. Los datos van
por el FT232RL; la energia, por la fuente a traves del INA226. La otra placa hace de medidora.

    Fuente (+) ---> INA226 VIN+   [shunt]   INA226 VIN- ---> pin 5V (o VIN) de la placa bajo prueba
    Fuente (-) -----------------------------------------> GND de la placa bajo prueba

    FT232RL (puente en 3.3 V)
       TXD ---> RX del ESP (GPIO3 / GPIO44)
       RXD <--- TX del ESP (GPIO1 / GPIO43)
       GND ---- GND
       VCC      SIN CONECTAR

    Placa medidora (la otra placa, por su USB al PC)
       3V3 ---> INA226 VCC
       GND ---> INA226 GND
       SDA ---> INA226 SDA     ESP32 clasico: GPIO21. ESP32-S3: GPIO8
       SCL ---> INA226 SCL     ESP32 clasico: GPIO22. ESP32-S3: GPIO9

    Analizador: CH1 (D0) GPIO4, CH2 (D1) GPIO5, GND, de la placa bajo prueba.

**Sin fuente regulada (montaje usado el 2026-11-12):** si el pin 5V de la medidora es solo entrada (serigrafia "5Vin", caso del S3),
alimentar la placa bajo prueba por su pin 3V3 desde el 3V3 de la medidora: 3V3 medidora a VIN+, VIN- a 3V3 de la placa bajo prueba.
Se mide sin el regulador de la placa; declararlo. Si el modulo INA226 trae pin VBUS (o VBS), puentearlo a VIN-: suelto, la tension
de bus lee 0.

Todas las GND quedan unidas: fuente (-), placa bajo prueba, INA226, medidora, FT232RL y analizador. Sin tierra comun el UART falla
y el INA226 mide mal la tension de bus.

Por que en el lado alto: el INA226 mide la tension de bus en VIN-, asi que la potencia sale de una sola lectura. En el lado bajo
la placa quedaria con su GND por encima de la tierra del FT232RL y del analizador.

Por que el pin 5V y no el 3V3: se mide la placa completa con su regulador, como pide `energy.py`. Lo atribuible a la inferencia
sale de la diferencia entre tramos, y el regulador se cancela en esa diferencia.

**Aviso sobre el puente USB de la placa:** en el montaje 3 el puente USB de la placa sigue conectado a GPIO1 y GPIO3 aunque no
tenga USB. Si queda alimentado desde el 5V de la placa, su TX choca con el del FT232RL y la comunicacion falla. Prueba en el paso
6.4. Si falla, hay que mover el protocolo a UART1 en otros pines (cambio de firmware, avisar antes de hacerlo).

## 4. Revision antes de energizar

Con todo desconectado de la corriente:

1. Multimetro en continuidad: todas las GND unidas entre si.
2. Multimetro en continuidad: no hay corto entre 5V y GND, ni entre 3V3 y GND, en cada placa.
3. FT232RL: puente en 3.3 V. Medir con el multimetro su TXD respecto a GND al conectarlo solo al PC: debe dar unos 3.3 V, nunca 5 V.
   El ESP32 no tolera 5 V en sus pines.
4. FT232RL: VCC sin conectar.
5. Fuente apagada: fijar **5.0 V** y limite de corriente en **500 mA** antes de conectarla. Una placa ESP32 sin WiFi suele quedar muy
   por debajo; si la fuente entra en limite, apagar y buscar el corto.
6. Nunca conectar el USB de la placa bajo prueba mientras la fuente la alimenta por 5V. Muchas placas unen VBUS del USB con el pin 5V
   a traves de un diodo o directamente; con ambos se pelean dos fuentes. **[CONFIRMAR]** en la placa si hay diodo, pero tratarlo
   siempre como prohibido.
7. INA226: el shunt de 0.1 ohm admite unos 0.82 A antes de saturar (81.92 mV de escala). Si el shunt real es otro, recalcular.

## 5. Preparar el PC

1. Instalar el controlador del puente USB de cada placa segun lo que diga su chip (CH340/CH343 de WCH o CP210x de Silicon Labs). El
   FT232RL usa el controlador VCP de FTDI.
2. Instalar PulseView. Si Windows no reconoce el analizador, usar Zadig para asignarle WinUSB, como indica sigrok.
3. Anotar el COM de cada dispositivo en el Administrador de dispositivos, conectandolos de a uno.
4. **Latency timer del FT232RL:** Administrador de dispositivos > Puertos > USB Serial Port > Propiedades > Configuracion de puerto >
   Opciones avanzadas > Latency Timer = **1 ms**. Anotar el valor. Los puentes CH340 y CP210x no tienen este ajuste; anotarlo
   tambien, porque explica diferencias en B05 entre montajes.
5. Activar el entorno: `C:\Users\Maicol\miniforge3\envs\latiniot\python.exe`, o `conda activate latiniot` desde la consola de Miniforge.

## 6. Primer encendido, placa por placa

### 6.1 Generar el firmware con los modelos entrenados

`firmware/inference/models_generated.c` lleva hoy un actor de ensayo. Antes de grabar, debe haber corrido `benchmark.run_all`, o:

    python -m analysis.export_models --seed 0
    powershell -File firmware\build_all.ps1

### 6.2 Grabar (montaje 1)

    . $HOME\esp\esp-idf\export.ps1
    cd firmware
    idf.py -B build_esp32 -p COMx flash        # placa A
    idf.py -B build_esp32s3 -p COMy flash      # placa B, por el conector COM/UART

Si no entra en modo de grabacion: mantener BOOT, pulsar y soltar EN/RST, soltar BOOT.

### 6.3 Leer `read_device_info`

Con `--port`, `host.experiment_runner` imprime `read_device_info` al conectar, en cualquier grupo. Basta un B01 corto
(`--samples 100`). Comprobar:

| Campo | Placa A esperado | Placa B esperado |
|---|---|---|
| chip | ESP32 | ESP32-S3 |
| cpu_mhz | 240 | 240 |
| flash | 4096 kB (el firmware usa 4 MB; si el modulo trae mas, se reporta 4 MB configurados) | 16384 kB |
| psram_kb | 0 | cerca de 8192. **Si da 0, la PSRAM no inicio** y no se sigue con esta placa |
| revision | La que traiga, se reporta | La que traiga |

### 6.4 Prueba del UART por el FT232RL (antes de B03)

Con la placa alimentada por la fuente (montaje 3, sin INA226 todavia, fuente directa al 5V con limite 500 mA) y el FT232RL:

    python -m host.experiment_runner --group B01 --port COMz --platform esp32 --samples 100

Si responde, el puente USB de la placa no estorba. Si hay tiempos de espera o tramas corruptas, ver el aviso de la seccion 3.

### 6.5 Paridad contra Python en silicio

Repetir la comprobacion de QEMU en la placa real: las acciones deben coincidir con Python con error menor a 1e-4 en FP32, INT16 e
INT8. Ninguna medida tiene sentido sin esto. Es la misma prueba que se hizo en QEMU, ahora por el puerto serie:

    python -m host.qemu_device esp32 --port COMx       # placa A
    python -m host.qemu_device esp32s3 --port COMy     # placa B

Resultado en `results/firmware/hw_parity_<objetivo>.json`; debe decir `"ok": true`. Prueba tambien que el firmware rechaza un
modelo inexistente, una observacion NaN y una trama corrupta.

## 7. Prueba de cada senal

1. **GPIO4 y GPIO5:** montaje 2, captura en PulseView a 24 MHz mientras corre B01. Deben verse pulsos en ambos canales; GPIO4 contenido
   dentro de GPIO5.
2. **UART a 921600:** en PulseView, decodificador UART en CH3 (D2) a 921600 8N1. Los bytes deben decodificarse sin errores de trama.
3. **INA226:** con la medidora grabada (seccion 9) y la fuente encendida pero la placa bajo prueba desconectada de VIN-:

       python -m host.energy_runner --check --meter-port COMy --shunt-ohm 0.1

   Debe dar `ina226_address` (la medidora la detecta sola entre 0x40 y 0x4F), `i_mean_a` cerca de 0, `v_mean` igual a la fuente
   y `sample_rate_hz` cerca de 1780 (medido 2026-11-12; cada muestra hace 3 lecturas I2C). Si dice que no encuentra el INA226, revisar SDA, SCL, VCC y GND.

## 8. Calibracion del shunt e incertidumbre (B03)

1. Medir la resistencia del shunt con el multimetro, con el modulo desconectado. Medir antes la resistencia de las puntas en corto y
   restarla. Con 0.1 ohm, la resolucion del multimetro domina: anotarla.
2. Mejor metodo: poner el multimetro en serie como amperimetro con una carga fija (por ejemplo una resistencia de potencia que tome
   entre 100 y 300 mA a 5 V) y comparar con la corriente del INA226. El cociente corrige el valor del shunt en `ina226_init`.
3. Comparar la tension de bus del INA226 con la del multimetro en VIN-.
4. Declarar en el articulo: exactitud del multimetro segun su hoja, resolucion del INA226 (2.5 uV de shunt, 1.25 mV de bus), shunt
   corregido y desviacion estandar de los tramos.

## 9. Codigo de B03

Escrito y probado sin hardware: la cadena completa con una medidora simulada de potencia conocida (`tests/test_energy_runner.py`) y
el firmware de la medidora en QEMU, que envia tramas que el host decodifica sin errores en ambos objetivos. Lo unico sin probar es
la lectura del INA226 real, que QEMU no emula.

- **Medidora:** `firmware/meter_app`, aplicacion ESP-IDF aparte. Detecta el INA226 por sus registros de identidad, convierte cada
  140 us sin promediado (medido: unas 1780 muestras por segundo, limitado por las lecturas I2C) y envia los registros crudos por su USB a 921600 baudios. Se graba en la
  placa que no se mide:

      . $HOME\esp\esp-idf\export.ps1
      cd firmware\meter_app
      idf.py -B build_esp32 -p COMy flash          # si la medidora es el ESP32 clasico; build_esp32s3 si es el S3

- **Host:** `host/energy_runner.py`. Reposo de 60 s, un tramo activo de 60 s por modelo (6 en total) a 50 Hz, y reposo otra vez:
  unos 8 min por placa. Recorta 1 s en cada borde, integra con el reloj de la medidora y reporta potencia, su error estandar por
  bloques de 1 s, energia por ciclo, energia atribuible por inferencia y la deriva entre los dos reposos.
- **Shunt:** el valor se pasa con `--shunt-ohm` y la conversion se hace en el PC. Calibrar no obliga a regrabar, y una medicion
  ya hecha se puede recalcular desde `raw.csv`.

## 10. Orden de las mediciones

Una placa a la vez. Primero la placa A, luego la B, mismo orden.

| Paso | Grupo | Montaje | Comando | Resultado |
|---|---|---|---|---|
| 1 | Paridad | 1 | seccion 6.5 | `results/firmware/` |
| 2 | B01 latencia | 1 o 2 | `python -m host.experiment_runner --group B01 --port COMx --platform esp32` | `results/B01/<id>/raw.csv` y `result.json` |
| 3 | B04 jitter | 1 o 2 | `... --group B04 --port COMx --platform esp32 --samples 100000` | `results/B04/<id>/` |
| 4 | B05 lazo cerrado | 2 | `... --group B05 --port COMx --platform esp32`, con captura de PulseView guardada | Captura `.sr` junto al resultado |
| 5 | B06 | 1 | `... --group B06 --port COMx --platform esp32 --episodes 50` | |
| 6 | B07 | 1 | `... --group B07 --port COMx --platform esp32 --episodes 50 --push-n 60`, repetir con 100 y 140 | |
| 7 | B03 energia | 3 | `python -m host.energy_runner --dut-port COMz --meter-port COMy --platform esp32 --shunt-ohm <calibrado>` | `results/B03/<id>/` |

Para la placa B cambiar `--platform esp32s3` y el puerto. Si B05 se mide tambien por el FT232RL, guardarlo como corrida aparte e
indicar el latency timer.

Anotar en cada sesion: fecha, placa, puerto, puente USB, latency timer, temperatura ambiente aproximada y version del firmware
(commit de git).

## 11. Fallos frecuentes

| Sintoma | Causa probable | Que hacer |
|---|---|---|
| Windows no ve la placa | Cable USB-C solo de carga, o falta el controlador | Probar otro cable; instalar CH340/CP210x |
| La placa no enciende con cargador USB-C a USB-C | Placa sin resistencias de 5.1 kohm en CC | Usar cable USB-A a USB-C |
| `idf.py flash` no conecta | No entra en modo de grabacion | BOOT + EN, ver 6.2; bajar velocidad con `-b 115200` |
| Sin respuesta tras grabar | Puerto equivocado (S3: conector OTG en vez de COM) | Usar el conector COM/UART |
| `psram_kb` = 0 en el S3 | PSRAM no inicio | Revisar que la placa sea N16R8; no seguir sin esto |
| Tramas corruptas por FT232RL | Puente USB de la placa interfiere, o falta GND comun | Seccion 3, aviso; revisar GND |
| GPIO4/GPIO5 planos en PulseView | Pin equivocado en la serigrafia o canal mal asignado | Revisar con el multimetro en modo diodo hasta el pin del modulo |
| PulseView pierde muestras | USB saturado | Bajar a 12 MHz o menos canales |
| Fuente entra en limite de corriente | Corto o conexion invertida | Apagar, revisar seccion 4 |
| `energy_runner` dice que no encuentra el INA226 | Cableado I2C, falta VCC, o pines distintos a GPIO21/22 (clasico) u 8/9 (S3) | Revisar con el multimetro; la direccion se detecta sola |
| Tension de bus del INA226 rara | Montaje en lado bajo o GND sin unir | Volver al esquema de la seccion 3 |
