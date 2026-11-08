# Fase 1: informe de inspeccion del URDF

Fecha: 2026-11-06. Archivo: `biped.urdf`, 13 322 bytes, UTF-8 sin BOM.
SHA-256: `bec0b7e2aa9444ebf15247446b99a3a6daaa1e251df11196e25241ac16d8d89d`.
El URDF original no se modifico. Datos crudos: `results/fase1/urdf_inspection.json`.

Fuentes: el URDF; el manuscrito `Desktop/Libros RNC/Bipedo.pdf` (version del 4 de julio de 2026, "el articulo");
el repositorio original https://github.com/kevin-ortega2724/RBIPEDO, commit `d1effbd` ("RBIPEDO", solo leido, no
ejecutado); mediciones propias en PyBullet 3.25 (conda-forge), API 202010061, Python 3.11.18, numpy 2.4.6, Windows 11.

## 1. Conclusion

- **El modelo carga directamente en PyBullet, sin cambios.** Ninguna modificacion es obligatoria para cargarlo.
- **No hay dependencias externas.** Cero mallas: toda la geometria es primitiva (box, cylinder, sphere).
- **Este es el URDF del entrenamiento.** El blob de RBIPEDO tiene el mismo SHA-256; un clon en Windows solo difiere por CRLF.
- **El URDF no define por si solo el robot simulado.** El entorno original cambia contacto, friccion y amortiguacion
  de tobillo por codigo (H15). Esos ajustes no estan en el articulo.
- **Queda una pregunta que solo responde el hardware** (D1: sentido de flexion de la rodilla) y tres confirmaciones
  (seccion 8).

## 2. Descripcion del modelo

| Propiedad | Valor | Verificacion |
|---|---|---|
| Nombre | `biped_robot` | XML |
| Enlaces / juntas | 13 / 12, todas `revolute` | XML y PyBullet |
| Base | `base_link` (pelvis), flotante: 6 + 12 = 18 GdL | PyBullet: indices q 7 a 18, u 6 a 17 |
| Topologia | dos cadenas serie de 6 juntas desde la pelvis | `parent_index` |
| Enlaces virtuales | 6 (`*_hip_yaw_link`, `*_hip_roll_link`, `*_ankle_link`), sin colision | XML |
| Masa total | 15.26 kg, de ellos 0.06 kg en enlaces virtuales | XML, PyBullet y seccion 6.4 del articulo |
| Altura cadera a suela | 0.77 m, igual a la altura de aparicion declarada | calculado |
| CoM en q=0 (marco base) | x = +0.0042, y = 0, z = -0.2745 m | calculado |
| Huella de cada pie | x de -0.02 a +0.10; y de +/-0.06 a +/-0.14 m | calculado |
| Margen del CoM en x | 0.024 m hacia el talon, 0.096 m hacia la punta | calculado |
| Etiquetas ausentes | `mesh`, `contact`, `transmission`, `mimic`, `gazebo` | XML |
| Transformaciones | todas las `rpy` son cero: los marcos son paralelos en q=0 | XML |

Convencion: x adelante, y izquierda, z arriba. La cadera yaw, roll y pitch comparten origen, igual que el
tobillo pitch y roll. El orden de PyBullet coincide con el del archivo y con `configs/task/t1_biped.yaml`
de rl-embedbench: `l_` y luego `r_`, en orden yaw, roll, pitch, rodilla, tobillo pitch, tobillo roll.

## 3. Tabla de articulaciones

| PB idx | Junta | Tipo | Padre | Hijo | Origen xyz (m) | Eje | Inf (rad) | Sup (rad) | Inf (grados) | Sup (grados) | Esfuerzo (N m) | Vel (rad/s) | Amort. | Fricc. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | l_hip_yaw | revolute | base_link | l_hip_yaw_link | [0.0, 0.1, 0.0] | [0.0, 0.0, 1.0] | -0.785 | 0.785 | -45.0 | 45.0 | 20.0 | 6.0 | 0.5 | 0.05 |
| 1 | l_hip_roll | revolute | l_hip_yaw_link | l_hip_roll_link | [0.0, 0.0, 0.0] | [1.0, 0.0, 0.0] | -0.524 | 0.524 | -30.0 | 30.0 | 30.0 | 6.0 | 0.5 | 0.05 |
| 2 | l_hip_pitch | revolute | l_hip_roll_link | l_thigh | [0.0, 0.0, 0.0] | [0.0, 1.0, 0.0] | -1.571 | 1.571 | -90.0 | 90.0 | 50.0 | 6.0 | 0.5 | 0.05 |
| 3 | l_knee_pitch | revolute | l_thigh | l_shank | [0.0, 0.0, -0.38] | [0.0, 1.0, 0.0] | -2.618 | 0.0 | -150.0 | 0.0 | 80.0 | 6.0 | 0.5 | 0.05 |
| 4 | l_ankle_pitch | revolute | l_shank | l_ankle_link | [0.0, 0.0, -0.36] | [0.0, 1.0, 0.0] | -0.785 | 0.785 | -45.0 | 45.0 | 30.0 | 6.0 | 0.3 | 0.02 |
| 5 | l_ankle_roll | revolute | l_ankle_link | l_foot | [0.0, 0.0, 0.0] | [1.0, 0.0, 0.0] | -0.524 | 0.524 | -30.0 | 30.0 | 20.0 | 6.0 | 0.3 | 0.02 |
| 6 | r_hip_yaw | revolute | base_link | r_hip_yaw_link | [0.0, -0.1, 0.0] | [0.0, 0.0, 1.0] | -0.785 | 0.785 | -45.0 | 45.0 | 20.0 | 6.0 | 0.5 | 0.05 |
| 7 | r_hip_roll | revolute | r_hip_yaw_link | r_hip_roll_link | [0.0, 0.0, 0.0] | [1.0, 0.0, 0.0] | -0.524 | 0.524 | -30.0 | 30.0 | 30.0 | 6.0 | 0.5 | 0.05 |
| 8 | r_hip_pitch | revolute | r_hip_roll_link | r_thigh | [0.0, 0.0, 0.0] | [0.0, 1.0, 0.0] | -1.571 | 1.571 | -90.0 | 90.0 | 50.0 | 6.0 | 0.5 | 0.05 |
| 9 | r_knee_pitch | revolute | r_thigh | r_shank | [0.0, 0.0, -0.38] | [0.0, 1.0, 0.0] | -2.618 | 0.0 | -150.0 | 0.0 | 80.0 | 6.0 | 0.5 | 0.05 |
| 10 | r_ankle_pitch | revolute | r_shank | r_ankle_link | [0.0, 0.0, -0.36] | [0.0, 1.0, 0.0] | -0.785 | 0.785 | -45.0 | 45.0 | 30.0 | 6.0 | 0.3 | 0.02 |
| 11 | r_ankle_roll | revolute | r_ankle_link | r_foot | [0.0, 0.0, 0.0] | [1.0, 0.0, 0.0] | -0.524 | 0.524 | -30.0 | 30.0 | 20.0 | 6.0 | 0.3 | 0.02 |

PyBullet reproduce exactamente limites, esfuerzos y velocidades del XML, y lee su amortiguacion y friccion.

## 4. Tabla de parametros fisicos

Unidades de inercia: kg m2, en el CoM; los productos de inercia son cero. Los 13 tensores son definidos
positivos y cumplen la desigualdad triangular. La ultima columna compara con el solido homogeneo; el error
maximo (0.07 %) es redondeo del propio URDF.

| Enlace | Masa (kg) | CoM xyz (m) | Ixx | Iyy | Izz | Visual | Colision | Err. rel. max vs solido |
|---|---|---|---|---|---|---|---|---|
| base_link | 5.0 | [0.0, 0.0, 0.0] | 0.020833 | 0.013542 | 0.026042 | box 0.15 0.20 0.10 | box 0.15 0.20 0.10 | 2.46e-05 |
| l_hip_yaw_link | 0.01 | [0.0, 0.0, 0.0] | 1e-06 | 1e-06 | 1e-06 | sphere 0.025 | ninguna | n/a |
| l_hip_roll_link | 0.01 | [0.0, 0.0, 0.0] | 1e-06 | 1e-06 | 1e-06 | sphere 0.025 | ninguna | n/a |
| l_thigh | 2.5 | [0.0, 0.0, -0.19] | 0.031083 | 0.031083 | 0.002 | cylinder 0.040 0.38 | cylinder 0.040 0.38 | 1.07e-05 |
| l_shank | 1.8 | [0.0, 0.0, -0.18] | 0.019845 | 0.019845 | 0.00081 | cylinder 0.030 0.36 | cylinder 0.030 0.36 | 0.00e+00 |
| l_ankle_link | 0.01 | [0.0, 0.0, 0.0] | 1e-06 | 1e-06 | 1e-06 | sphere 0.020 | ninguna | n/a |
| l_foot | 0.8 | [0.04, 0.0, -0.015] | 0.000487 | 0.00102 | 0.001387 | box 0.12 0.08 0.03 | box 0.12 0.08 0.03 | 6.85e-04 |
| r_hip_yaw_link | 0.01 | [0.0, 0.0, 0.0] | 1e-06 | 1e-06 | 1e-06 | sphere 0.025 | ninguna | n/a |
| r_hip_roll_link | 0.01 | [0.0, 0.0, 0.0] | 1e-06 | 1e-06 | 1e-06 | sphere 0.025 | ninguna | n/a |
| r_thigh | 2.5 | [0.0, 0.0, -0.19] | 0.031083 | 0.031083 | 0.002 | cylinder 0.040 0.38 | cylinder 0.040 0.38 | 1.07e-05 |
| r_shank | 1.8 | [0.0, 0.0, -0.18] | 0.019845 | 0.019845 | 0.00081 | cylinder 0.030 0.36 | cylinder 0.030 0.36 | 0.00e+00 |
| r_ankle_link | 0.01 | [0.0, 0.0, 0.0] | 1e-06 | 1e-06 | 1e-06 | sphere 0.020 | ninguna | n/a |
| r_foot | 0.8 | [0.04, 0.0, -0.015] | 0.000487 | 0.00102 | 0.001387 | box 0.12 0.08 0.03 | box 0.12 0.08 0.03 | 6.85e-04 |

## 5. Compatibilidad con PyBullet

| Prueba | Resultado |
|---|---|
| Carga en DIRECT, 12 juntas | Correcto |
| 2 s con h=1 ms, 50 iteraciones, `numSubSteps` 0 y 4, q=0 sostenido por el motor interno | Sin NaN, pelvis estable en z=0.76999 m |
| Fuerza normal total con `numSubSteps=0` | 149.71 N (peso: 149.70 N) |
| Fuerza normal total con `numSubSteps=4` | 37.42 N, ver H3 |
| Fuerza normal con los ajustes de RBIPEDO, 0.2 a 0.5 s | unos 37.5 N con 4 subpasos, unos 150 N con 0 |
| Juntas bloqueadas con los ajustes de RBIPEDO | Vuelca antes de 2 s, sin NaN, ver H19 |
| Rendimiento (solo fisica, un proceso, i5-10500T) | unos 1050 pasos/s con 4 subpasos; unos 4170 con 0 |

La prueba sostiene q=0 con el motor interno solo para verificar carga y contacto. No valida el controlador
PD ni la postura de pie, que son de las fases 2 y 3. GUI no probada (la fase 1 corre en DIRECT).

## 6. Dependencias y configuracion original

**Del modelo:** ninguna. No hay rutas de mallas que verificar.

**Encontrado en RBIPEDO:** entorno, agente SAC, curriculum, parametros y logs de entrenamiento.

**Sigue sin aparecer:** `control/leg_dynamics.py`, `td3/results/el_consistency_audit.npz`, `training_log_sac*.npz` y todos
los checkpoints `.pt` (excluidos por `.gitignore`; no estan en ninguno de los 23 commits). Los checkpoints no bloquean:
la politica original es por torque y hay que reentrenar.

### Observacion real (`td3/curriculum_env.py`, lineas 122 a 134)

| Indices | Variable | Transformacion |
|---|---|---|
| 0 a 11 | posiciones articulares (rad), orden de `JOINT_NAMES` | recorte a +/-pi |
| 12 a 23 | velocidades articulares (rad/s) | recorte a +/-20 |
| 24 | altura de pelvis | (z-0.77)/0.77, sin recorte |
| 25 a 27 | roll, pitch, yaw de `getEulerFromQuaternion` | sin recorte |
| 28 a 30 | velocidad lineal de `getBaseVelocity`, marco mundo | recorte a +/-5 |
| 31 a 33 | velocidad angular de `getBaseVelocity`, marco mundo | recorte a +/-10 |
| 34, 35 | fuerza normal de pie izquierdo y derecho | F/300, recorte a [0, 1]; afectada por H3 |

La expresion (z-0.40)/0.37 es de la recompensa, no de la observacion.

### Parametros: articulo, codigo y esta implementacion

| Parametro | Articulo | Codigo RBIPEDO | Esta implementacion |
|---|---|---|---|
| Paso fisico / control | 1 ms / 20 ms | Igual | Igual |
| `numSolverIterations` / `numSubSteps` | 50 / 4 | Igual | Propuesto: igual |
| Inercias | No dice | `URDF_USE_INERTIA_FROM_FILE` | Igual |
| Autocolision | No dice | Desactivada | Igual |
| Motores por defecto | No dice | Desactivados (`force=0`) | Igual |
| Friccion de suelo y pies | mu=0.6 solo en simulador de referencia | 0.6, restitucion 0 | D5 |
| Rigidez y amortiguacion de contacto del pie | No dice | 1e4 y 50 | D5 |
| Amortiguacion de tobillo | No dice (URDF: 0.3) | **3.0** | 0.3, ver nota de D5 |
| Accion | torque | a * `MAX_TORQUES` | Posicion + PD: exige reentrenar |
| Caida | No dice | z<0.40, o abs(roll)>1.2, o abs(pitch)>1.2 | Igual |
| Estado inicial | No dice | q=0, velocidad 0, z=0.77, sin aleatoriedad | Igual en entrenamiento; ver H18 para evaluacion |
| Episodio | 10 s / 6 s | 500 / 300 pasos | Igual |
| Actor | 36-256-256-12 | Comun + `mu_head` + `log_std_head`; log_std en [-5, 2]; determinista tanh(mu) | Igual; 64-64 es propuesto |
| Ganancias PD | No aplica | `PID_KP` 30, 50, 300, 200, 80, 30 y `PID_KD` 1, 2, 4, 3, 2, 1 por pierna, solo para demos | Punto de partida; validar en fase 3 |
| Calendario | 40 k / 1.6 M / 3 M | Depende de la corrida, ver H16 | D6 |

Las corridas originales fueron en Linux, con PyBullet compilado en enero de 2025; esta implementacion usa otra compilacion.

## 7. Problemas detectados

Severidad alta: cambia resultados o invalida comparaciones. Media: hay que manejarla en codigo. Baja: documental.

### Alta

**H1. La rodilla flexiona hacia la punta del pie.** Eje +Y, limites [-2.618, 0]. Medido: con q=-1 rad el tobillo
va a x=+0.303 m, hacia adelante, y la punta del pie tambien esta en +x. El comentario de la linea 182 dice
"bends backward". La rama arccos de la ecuacion (6) da theta4 >= 0, y con los mismos ejes (la tabla DH coincide
con el URDF en los seis ejes) el tobillo iria a x=-0.173 m con theta4=+0.5: el sentido opuesto, fuera del
rango del URDF. La recompensa premia +x, asi que la marcha aprendida usaria una rodilla invertida respecto a la
anatomia humana. No esta probado si esto contribuyo al optimo local de marcha hacia atras; es una hipotesis.
El codigo original usa negativo como flexion en todas partes (`gait_generator.py`, `move.py`), y su cinematica inversa
usa arccos con theta4 >= 0, como el articulo. El video de la marcha no permite decidirlo. Falta confirmar en cual
sentido flexiona el ARON real.

**H2. El tramo tobillo a suela no coincide con el modelo certificado.** En la Fig. 1a y la tabla 1, `l6`=0.12 m
es la distancia vertical del tobillo a la suela, y la pierna mide 0.86 m. El URDF usa 0.12 m como largo del pie
y deja 0.03 m bajo el tobillo: 0.77 m. La seccion 8.1 afirma que el URDF sale "exactamente" de esos parametros.
El codigo confirma que se entreno con 0.77 m (`STANDING_HEIGHT = l3 + l4 + FOOT_HEIGHT`), mientras `DH_PARAMS` usa 0.12,
y `dh_to_urdf.py` admite que las dos convenciones difieren. Su offset calibrado no se usa en ningun otro modulo. La
metrica M1 no cubre este tramo del URDF.

**H3. Con `numSubSteps=4`, `getContactPoints` reporta un cuarto de la fuerza.** Medido en reposo: 37.42 N contra
149.71 N. Relacion 4.00. Con los ajustes reales del entorno se repite: unos 37.5 N contra unos 150 N entre 0.2 y 0.5 s. El entrenamiento original
leyo `getContactPoints` con 4 subpasos y dividio por 300, asi que su divisor efectivo fue 1200 N: de pie, cada pie
observaba unos 0.06 en lugar de 0.25. Fue consistente durante el entrenamiento, pero el valor no es la fuerza fisica.
Solo se verifico cerca del reposo; falta comprobarlo en impacto (fase 2).

**H4. Sin `URDF_USE_INERTIA_FROM_FILE`, PyBullet ignora las inercias del URDF.** Las recalcula desde la colision:
muslo Ixx +4.8 % e Izz +54.1 %; tibia Ixx +4.5 % e Izz +61.3 %; enlaces virtuales 6.67e-9 en vez de 1e-6. La carga
por defecto no usa los tensores certificados. El entorno original si activa la bandera; esta implementacion tambien.
`calibrate_dh_offset.py` no la activa, pero solo usa cinematica.

**H15. El robot simulado no es solo el URDF.** `envs/biped_env.py` fija rigidez de contacto 1e4, amortiguacion de contacto 50,
friccion 0.6, restitucion 0, y sube la amortiguacion de tobillo de 0.3 a 3.0 (10 veces). El articulo no lo menciona.
Sin replicarlo, el entorno no es comparable con el original.

**H16. El calendario de la corrida principal no es el del articulo.** La tabla 6 declara fase 3 desde 1.6 M para Exps. 3 y 4, y la
seccion 9.6 dice que las semillas usan el mismo calendario. Los logs dicen otra cosa:

| Log | Workers | Fase 3 desde | vx media, pasos >= 1.6 M | Evaluaciones positivas |
|---|---|---|---|---|
| `sac_v3` (Exp. 4) | 6 | **160 k** | +1.244 | 98.6 % |
| `sac_v3_seed1` | 4 | 1.6 M | +0.621 | 100 % |
| `sac_v3_seed2` | 4 | 1.6 M | +0.909 | 100 % |

Las cifras de la tabla 10 si se reproducen, pero la corrida principal paso 2.84 M pasos en fase 3 y las semillas 0.4 M, con
distinto numero de workers. La dispersion entre semillas mezcla esos tres factores. El log de Exp. 3 no esta en el repositorio.

### Media

**H5. Autocolision en reposo.** Con `URDF_USE_SELF_COLLISION`, incluso con `EXCLUDE_PARENT`, en q=0 hay
interpenetracion muslo y pelvis (-41 mm) y pie y tibia (-1 mm), porque no son padre e hijo directos. Por defecto
esta desactivada, y asi entreno el original. Activarla exige filtrar esos 4 pares; desactivarla permite que las piernas
se crucen.

**H6. El motor por defecto anula el torque.** Medido con 0.2 N m durante 50 ms: 2.06 rad/s con el motor
desactivado, 0.00006 rad/s con el activo. El original lo desactiva en `reset()`; el PD de la fase 3 debe hacer lo mismo.

**H7. La amortiguacion del URDF si actua y la friccion no.** Inercia efectiva medida en la cadera yaw: 0.0049 kg m2.
Con 3 rad/s iniciales y 0.2 s: queda 0.001 rad/s con amortiguacion del URDF; 2.86 rad/s sin ella; 2.94 sin la
amortiguacion por defecto de Bullet. Una friccion de 0.05 N m habria quitado unos 2 rad/s, asi que no se aplica.
El articulo declara actuadores ideales "sin friccion", pero la amortiguacion viscosa de 0.3 a 0.5 N m s/rad esta
activa, y en los tobillos el codigo la sube a 3.0 (H15). Esto tambien vale para el PD: se suma al termino Kd.

**H8. La accion cero no es de pie.** Con la formula q_ref del encargo, la rodilla tiene q_mid=-1.309 rad (-75 grados).
Pierna recta (q=0) exige a=+1, justo en el tope y en saturacion de tanh. Ademas q=0 esta en el limite articular.
Afecta a la exploracion inicial de SAC y a la sensibilidad a la cuantizacion. Se resuelve en las fases 3 y 5.

**H9. Masa inconsistente en el articulo.** 15.26 kg (seccion 6.4, igual al URDF) frente a 12 kg en la tabla 12 y en
la seccion 9.8 para "Ours". 15.26 incluye los 0.06 kg virtuales.

**H10. Trazabilidad incompleta.** El encabezado atribuye los parametros a la tabla 2, pero esta solo da longitudes
y masas. Radios, dimensiones de pelvis y pie, separacion de cadera, limites, esfuerzos, velocidades, amortiguacion
y friccion no estan en el articulo. `configs/robot_params.py` repite casi todos, pero es del mismo proyecto y llama
"estimate" a la masa de la pelvis. Se tratan como autoritativos, sin fuente independiente de hardware.

**H11. Mal condicionamiento potencial.** Razon de inercias 31 083:1 entre muslo y enlace virtual, y razon de masas
500:1 entre pelvis y enlace virtual. Sin problemas en 2 s de reposo; no probado bajo impactos.

**H12. Ejes no espejados.** Las dos piernas tienen ejes identicos: hip_roll +0.3 rad abre la pierna izquierda (y=+0.319)
y cierra la derecha (y=+0.119). Yaw y roll necesitan signo invertido para marchas simetricas. No es un error.

**H17. La velocidad de evaluacion no se mide como dice el articulo.** La seccion 8.2 habla de desplazamiento de pelvis sin
recortar. `info["v_x"]` es `base_lin_vel[0]`, instantanea al final de cada paso de control. El benchmark debe usar
desplazamiento y declararlo.

**H18. Semillas y evaluacion insuficientes para reproducir.** Solo se siembra numpy; ni torch ni los workers. `reset()` no tiene
aleatoriedad y la politica de evaluacion es determinista, pero 227 de 300 evaluaciones de la corrida principal tienen
desviacion mayor que 0. La causa no esta identificada. Los 5 episodios no son muestras controladas: B06 y B07 necesitan
perturbacion inicial sembrada.

*Actualizacion (fase 3):* una causa de no determinismo aqui fue la fuerza de contacto que `restoreState` deja de la
corrida anterior; `reset` la pone a cero y el entorno es repetible bit a bit. No se comprobo que sea la causa en RBIPEDO, que no se ejecuto.

**H19. Con juntas bloqueadas y los ajustes de contacto originales, el robot vuelca hacia atras.** Medido: pitch -0.21 rad a 1 s
y pelvis en el suelo antes de 2 s, con el CoM dentro de la huella. Con contacto rigido se mantuvo los 2 s. Causa no
determinada. Pararse exige control activo; los ensayos de postura van en la fase 3.

*Actualizacion (fase 3):* explicado. El contacto blando
de penalizacion deja poca reserva de apoyo (CoM a 24 mm del talon): basta para volcar sin control activo.

**H20. Observaciones con escalas muy distintas.** Van de +/-1 a +/-20 sin normalizar. Una escala unica en INT8 perderia casi toda
la resolucion en las variables pequenas; la fase 6 debe usar escala por variable y medirlo.

### Baja

- H13. Linea 69: dice "no mass", pero los enlaces virtuales tienen 0.01 kg.
- H14. Ecuacion (20) aplicada literalmente con P'=l/2 daria 0.090 kg m2 en el muslo; el URDF usa el cilindro
  solido (0.031). Sigue abierto: `leg_dynamics.py` no esta en el repositorio.

### Fuera de alcance, en el manuscrito

- Lineas 693 y 694: +2.38 m/s se describe "above the 3.3 m/s Unitree H1 record".
- Linea 618: retorno de Exp. 2 igual a +217; la tabla 8 dice +144.1.
- Seccion 8.1.1: 0.53 N m RMS de torque parece bajo para sostener 15 kg en marcha. No verificable: el script de la
  auditoria no esta en el repositorio.
- Numeracion de experimentos: el README de RBIPEDO llama Exp. 3 a la corrida que el articulo llama Exp. 4.

## 8. Decisiones (ninguna modificacion del URDF)

| Id | Decision | Estado y recomendacion |
|---|---|---|
| D1 | Rodilla: mantener el URDF o invertir limites a [0, 2.618] | **Abierta, depende del ARON real.** Mantener si flexiona como en el URDF; si no, corregir en copia adaptada y declararlo |
| D2 | `numSubSteps` y fuerza de contacto | Confirmado 4 en el original. Propuesta: 4, y fuerza fisica corregida (multiplicar por 4, tras verificar en impacto) antes de dividir por 300 |
| D3 | Tobillo a suela | Resuelta: 0.03 m, como se entreno; declarar la diferencia con la DH |
| D4 | Codigo original | Resuelta en lo necesario: se adoptan las convenciones de la seccion 6 |
| D5 | Replicar ajustes de contacto y tobillo (H15) | Contacto: si, en configuracion externa. **Tobillo: se aparta de lo propuesto, queda 0.3 del URDF.** Con 3.0 la junta se pega (d dt/I cerca de 6) y el seguimiento del PD tiene 41 % de error |
| D6 | Calendario de entrenamiento (H16) | Propuesta: 40 k / 160 k / 3 M, el que produjo +1.24 m/s, igual para ambas arquitecturas y todas las semillas |

Sin cambios en el archivo URDF se resuelven en codigo: H4 (bandera), H6 (desactivar motores), H12 (mapa de signos),
H15 (configuracion externa), H17 y H18 (metrica y semillas). H13 es solo un comentario.

## 9. Plan de validacion (fase 2)

| Prueba | Criterio de aceptacion |
|---|---|
| Cinematica URDF frente a DH en 1000 configuraciones, incluyendo el tramo de H2 | Error de tobillo < 1 mm (umbral M1) |
| Masa, CoM e inercias leidas de PyBullet frente al XML | Igualdad numerica |
| Fuerza de contacto con subpasos, en reposo y en impacto | Factor explicado; suma igual al peso en reposo con error < 1 % |
| Caida libre sin contacto | Aceleracion de CoM igual a g; momento angular constante |
| Limites articulares bajo torque maximo | Sobrepaso medido y reportado |
| Esfuerzo y velocidad maximos en control por torque | Verificar si PyBullet los aplica; si no, saturar en codigo |
| Estabilidad numerica con impactos (H11) | Sin NaN ni explosion en 1000 episodios aleatorios |
| Entorno con los ajustes de H15 | Valores leidos de PyBullet iguales a la configuracion |
| Determinismo: mismo `reset` y acciones fijas, dos veces en un proceso | Trayectorias iguales, o causa de H18 identificada |
| Inspeccion en GUI | Revision visual del sentido de cada junta |

## 10. Archivos y pruebas

| Archivo | Funcion |
|---|---|
| `robot/urdf/biped.urdf` | Copia byte a byte del original |
| `analysis/inspect_urdf.py` | Extrae todo del XML y ejecuta las mediciones en PyBullet |
| `tests/test_urdf_inspection.py` | 12 pruebas que fijan los hechos de este informe |
| `results/fase1/urdf_inspection.json`, `tables.md` | Datos crudos y tablas |
| `environment.yml` | Entorno fijado; reemplaza a `requirements.txt` porque PyPI no tiene wheel de PyBullet para Windows en 3.12 y 3.13 |

Entorno: con MKL 2026.1 numpy muere al multiplicar matrices (excepcion 0xC06D007F); se fijo OpenBLAS.
