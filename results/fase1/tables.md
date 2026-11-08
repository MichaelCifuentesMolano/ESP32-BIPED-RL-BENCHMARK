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
