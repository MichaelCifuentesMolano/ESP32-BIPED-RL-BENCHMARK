"""Entorno del bipedo: 12 acciones normalizadas, control por posicion a 50 Hz, fisica a 1 kHz."""
import numpy as np
import pybullet as p
import pybullet_data
from pybullet_utils.bullet_client import BulletClient

from simulation.biped_controller import PDController
from simulation.observations import build_observation
from simulation.rewards import compute_reward, phase_weights
from simulation.simulation_config import ROOT, load_config


class BipedEnv:
    def __init__(self, cfg=None, gui=False, max_steps=None):
        self.cfg = cfg or load_config()
        self.max_steps = max_steps or self.cfg["episode"]["train_steps"]
        ph, ct = self.cfg["physics"], self.cfg["contact"]
        self.ctrl_dt = ph["dt"] * ph["steps_per_action"]
        # shortcut: PyBullet reporta la fuerza de un subpaso dividida por el paso completo (H3); factor verificado en tests.
        self.force_gain = max(ph["num_sub_steps"], 1)

        self.bc = bc = BulletClient(connection_mode=p.GUI if gui else p.DIRECT)
        bc.setAdditionalSearchPath(pybullet_data.getDataPath())
        bc.setGravity(0, 0, ph["gravity"])
        bc.setPhysicsEngineParameter(fixedTimeStep=ph["dt"], numSolverIterations=ph["solver_iterations"],
                                     numSubSteps=ph["num_sub_steps"])
        self.plane = bc.loadURDF("plane.urdf")
        bc.changeDynamics(self.plane, -1, lateralFriction=ct["friction"], restitution=ct["restitution"])
        h = self.cfg["robot"]["spawn_height"]
        self.robot = bc.loadURDF(str(ROOT / self.cfg["robot"]["urdf"]), [0, 0, h], flags=p.URDF_USE_INERTIA_FROM_FILE)

        info = {}
        for i in range(bc.getNumJoints(self.robot)):
            ji = bc.getJointInfo(self.robot, i)
            info[ji[1].decode()] = ji
        names = self.cfg["robot"]["action_order"]
        self.joint_ids = [info[n][0] for n in names]
        self.feet = [info["l_ankle_roll"][0], info["r_ankle_roll"][0]]  # el hijo de ankle_roll es el pie
        for foot in self.feet:
            bc.changeDynamics(self.robot, foot, lateralFriction=ct["friction"], restitution=ct["restitution"],
                              contactStiffness=ct["foot_stiffness"], contactDamping=ct["foot_damping"])
        for n in names:
            if "ankle" in n:
                bc.changeDynamics(self.robot, info[n][0], jointDamping=ct["ankle_joint_damping"])
        # Limites y torques siempre del URDF; ganancias de la configuracion, iguales en ambas piernas.
        c = self.cfg["control"]
        self.controller = PDController([info[n][8] for n in names], [info[n][9] for n in names],
                                       [info[n][10] for n in names], c["kp"] * 2, c["kd"] * 2)
        self._free_motors()
        self._initial_state = bc.saveState()
        self.rng = np.random.default_rng(0)
        self.push = None
        self.steps = 0
        self.x_prev = 0.0

    def _free_motors(self):
        self.bc.setJointMotorControlArray(self.robot, self.joint_ids, p.VELOCITY_CONTROL, forces=[0.0] * 12)

    def seed(self, seed):
        self.rng = np.random.default_rng(seed)

    def reset(self, noise=0.0):
        """Estado exacto guardado tras la carga; con noise, perturbacion uniforme sembrada en q (rad)."""
        self.bc.restoreState(self._initial_state)
        self._free_motors()
        if noise:
            lo = self.controller.q_mid - self.controller.q_half
            hi = self.controller.q_mid + self.controller.q_half
            for j, q in zip(self.joint_ids, np.clip(self.rng.uniform(-noise, noise, 12), lo, hi)):
                self.bc.resetJointState(self.robot, j, float(q), 0.0)
        self.steps, self.push, self.x_prev = 0, None, 0.0
        raw = self.read_state()
        raw["foot_forces"] = [0.0, 0.0]  # tras restoreState getContactPoints devuelve la fuerza del episodio anterior
        return build_observation(raw, self.cfg)

    def read_state(self):
        bc, r = self.bc, self.robot
        js = bc.getJointStates(r, self.joint_ids)
        pos, orn = bc.getBasePositionAndOrientation(r)
        lin, ang = bc.getBaseVelocity(r)
        forces = [self.force_gain * sum(c[9] for c in bc.getContactPoints(r, self.plane, f, -1)) for f in self.feet]
        return {"q": np.array([s[0] for s in js]), "qd": np.array([s[1] for s in js]), "pos": np.array(pos),
                "euler": np.array(bc.getEulerFromQuaternion(orn)), "lin_vel": np.array(lin), "ang_vel": np.array(ang),
                "foot_forces": forces}

    def apply_push(self, force_xyz, duration_s):
        """Empuje externo en la pelvis, marco mundo, durante los proximos duration_s."""
        self.push = [list(force_xyz), int(round(duration_s / self.cfg["physics"]["dt"]))]

    def _fallen(self, pos, orn):
        t = self.cfg["termination"]
        roll, pitch, _ = self.bc.getEulerFromQuaternion(orn)
        return pos[2] < t["min_height"] or abs(roll) > t["max_tilt"] or abs(pitch) > t["max_tilt"]

    def step(self, action, weights=None):
        """Avanza un periodo de control. Devuelve obs, recompensa, terminado, truncado, info."""
        bc, r, ctl = self.bc, self.robot, self.controller
        q_ref = ctl.reference(action)
        energy, n, fallen, peak = 0.0, 0, False, 0.0
        for _ in range(self.cfg["physics"]["steps_per_action"]):
            js = bc.getJointStates(r, self.joint_ids)
            tau = ctl.torque(q_ref, np.array([s[0] for s in js]), np.array([s[1] for s in js]))
            bc.setJointMotorControlArray(r, self.joint_ids, p.TORQUE_CONTROL, forces=tau.tolist())
            if self.push and self.push[1] > 0:
                bc.applyExternalForce(r, -1, self.push[0], [0, 0, 0], p.LINK_FRAME)
                self.push[1] -= 1
            bc.stepSimulation()
            energy += float(np.sum((tau / ctl.tau_max) ** 2))
            peak = max(peak, float(np.max(np.abs(tau))))
            n += 1
            pos, orn = bc.getBasePositionAndOrientation(r)
            if self._fallen(pos, orn):
                fallen = True
                break
        self.steps += 1
        raw = self.read_state()
        obs = build_observation(raw, self.cfg)
        x = float(raw["pos"][0])
        v_x = (x - self.x_prev) / self.ctrl_dt
        self.x_prev = x
        w = weights if weights is not None else phase_weights(10**12, self.cfg)[0]
        energy /= n
        roll, pitch = float(raw["euler"][0]), float(raw["euler"][1])
        reward = compute_reward(w, v_x, float(raw["pos"][2]), roll, pitch, energy, fallen, self.cfg)
        truncated = self.steps >= self.max_steps
        info = {"v_x": v_x, "x": x, "z": float(raw["pos"][2]), "roll": roll, "pitch": pitch, "energy": energy,
                "fallen": fallen, "foot_forces": raw["foot_forces"], "peak_torque": peak, "q_ref": q_ref, "q": raw["q"]}
        return obs, reward, fallen, truncated, info

    def close(self):
        self.bc.disconnect()
