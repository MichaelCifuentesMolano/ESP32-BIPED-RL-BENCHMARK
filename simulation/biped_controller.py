"""Control por posicion: accion normalizada a referencia articular y PD saturado."""
import numpy as np


class PDController:
    def __init__(self, q_min, q_max, tau_max, kp, kd):
        self.q_mid = (np.asarray(q_max) + np.asarray(q_min)) / 2
        self.q_half = (np.asarray(q_max) - np.asarray(q_min)) / 2
        self.tau_max = np.asarray(tau_max, float)
        self.kp = np.asarray(kp, float)
        self.kd = np.asarray(kd, float)

    def reference(self, action):
        """q_ref = q_mid + a * (q_max - q_min) / 2, con a recortada a [-1, 1]."""
        return self.q_mid + np.clip(action, -1.0, 1.0) * self.q_half

    def action_for(self, q_ref):
        """Inversa de reference: accion que produce q_ref."""
        return (np.asarray(q_ref) - self.q_mid) / self.q_half

    def torque(self, q_ref, q, qd):
        return np.clip(self.kp * (q_ref - q) - self.kd * qd, -self.tau_max, self.tau_max)
