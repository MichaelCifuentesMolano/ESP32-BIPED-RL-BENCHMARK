"""Fases 2, 3 y 4: entorno, controlador PD, observaciones y recompensa."""
import copy

import numpy as np
import pybullet as p
import pytest

from analysis.inspect_urdf import DEFAULT_URDF, parse_urdf
from simulation.biped_controller import PDController
from simulation.observations import NAMES, OBS_DIM, ObservationStats, build_observation
from simulation.pybullet_env import BipedEnv
from simulation.rewards import compute_reward, phase_weights
from simulation.simulation_config import load_config

CFG = load_config()
MASS = 15.26
G = 9.81


@pytest.fixture
def env():
    e = BipedEnv()
    yield e
    e.close()


def lock_joints(e):
    e.bc.setJointMotorControlArray(e.robot, e.joint_ids, p.POSITION_CONTROL, targetPositions=[0.0] * 12,
                                   forces=[2000.0] * 12, positionGains=[1.0] * 12, velocityGains=[1.0] * 12)


# ---- Fase 2: entorno ----

def test_joint_mapping_and_limits_come_from_urdf(env):
    model = parse_urdf(DEFAULT_URDF)
    for i, (name, jid) in enumerate(zip(CFG["robot"]["action_order"], env.joint_ids)):
        info = env.bc.getJointInfo(env.robot, jid)
        assert info[1].decode() == name
        j = model["joints"][name]
        assert env.controller.q_mid[i] - env.controller.q_half[i] == pytest.approx(j["lower"])
        assert env.controller.q_mid[i] + env.controller.q_half[i] == pytest.approx(j["upper"])
        assert env.controller.tau_max[i] == j["effort"]


def test_physical_parameters_reach_pybullet(env):
    model = parse_urdf(DEFAULT_URDF)
    total = env.bc.getDynamicsInfo(env.robot, -1)[0]
    for i in range(env.bc.getNumJoints(env.robot)):
        ji = env.bc.getJointInfo(env.robot, i)
        d = env.bc.getDynamicsInfo(env.robot, i)
        link = model["links"][ji[12].decode()]
        total += d[0]
        assert d[0] == pytest.approx(link["mass"])
        assert d[2] == pytest.approx((link["inertia"]["ixx"], link["inertia"]["iyy"], link["inertia"]["izz"]))
    assert total == pytest.approx(MASS)


def test_original_contact_settings_applied(env):
    c = CFG["contact"]
    for foot in env.feet:
        d = env.bc.getDynamicsInfo(env.robot, foot)
        assert (d[1], d[5], d[8], d[9]) == (c["friction"], c["restitution"], c["foot_damping"], c["foot_stiffness"])


def test_reset_is_exactly_reproducible(env):
    """H18: mismas acciones tras reset dan la misma trayectoria, bit a bit."""
    actions = np.random.default_rng(1).uniform(-0.2, 0.2, (40, 12)) + env.controller.action_for(np.zeros(12))

    def rollout():
        out = [env.reset()]
        for a in actions:
            out.append(env.step(a)[0])
            if env.steps >= 40:
                break
        return np.array(out)

    a, b = rollout(), rollout()
    assert np.array_equal(a, b)


def test_seeded_reset_noise(env):
    env.seed(5)
    a = env.reset(0.02)
    env.seed(5)
    b = env.reset(0.02)
    c = env.reset(0.02)
    assert np.array_equal(a, b) and not np.array_equal(a, c)
    assert np.abs(a[:12]).max() <= 0.02


def test_free_fall_matches_gravity():
    cfg = copy.deepcopy(CFG)
    cfg["robot"]["spawn_height"] = 5.0
    e = BipedEnv(cfg)
    for i in range(-1, e.bc.getNumJoints(e.robot)):  # arrastre por defecto de Bullet: resta 4 % en 0.3 s (declarado)
        e.bc.changeDynamics(e.robot, i, linearDamping=0.0, angularDamping=0.0)
    for _ in range(300):
        e.bc.stepSimulation()
    v = e.bc.getBaseVelocity(e.robot)[0][2]
    e.close()
    assert v == pytest.approx(-G * 0.3, rel=0.001)


def test_contact_force_correction_holds_on_impact():
    """H3 en impacto: la suma de fuerza corregida por dt debe igualar el cambio de cantidad de movimiento."""
    cfg = copy.deepcopy(CFG)
    cfg["robot"]["spawn_height"] = 0.82
    e = BipedEnv(cfg)
    lock_joints(e)
    dt = cfg["physics"]["dt"]
    impulse, peak, v0 = 0.0, 0.0, None
    steps = 0
    for _ in range(400):
        e.bc.stepSimulation()
        steps += 1
        f = sum(e.read_state()["foot_forces"])
        if f > 0 and v0 is None:
            v0, steps_in_contact = e.bc.getBaseVelocity(e.robot)[0][2], 0
        if v0 is not None:
            impulse += f * dt
            peak = max(peak, f)
            steps_in_contact += 1
    v1 = e.bc.getBaseVelocity(e.robot)[0][2]
    e.close()
    expected = MASS * (v1 - v0) + MASS * G * steps_in_contact * dt
    assert v0 < -0.5 and peak > 2 * MASS * G
    assert impulse == pytest.approx(expected, rel=0.10)


def test_push_changes_velocity(env):
    a = env.controller.action_for(np.zeros(12))
    env.reset()
    env.apply_push([300.0, 0, 0], 0.02)
    env.step(a)
    assert env.bc.getBaseVelocity(env.robot)[0][0] > 0.1


def test_fall_terminates_and_is_penalized(env):
    env.reset()
    for _ in range(200):
        _, r, term, _, info = env.step(np.zeros(12))
        if term:
            break
    assert term and info["fallen"] and r < -40


def test_truncation_flag():
    e = BipedEnv(max_steps=3)
    e.reset()
    flags = [e.step(e.controller.action_for(np.zeros(12)))[3] for _ in range(3)]
    e.close()
    assert flags == [False, False, True]


# ---- Fase 3: controlador ----

def controller():
    return PDController([-1, -2], [1, 0], [10, 20], [100, 100], [5, 5])


def test_action_mapping_formula():
    c = controller()
    assert np.allclose(c.reference([0, 0]), [0, -1])
    assert np.allclose(c.reference([1, 1]), [1, 0])
    assert np.allclose(c.reference([-1, -1]), [-1, -2])
    assert np.allclose(c.reference([5, -5]), [1, -2])  # recorte
    assert np.allclose(c.action_for(c.reference([0.3, -0.7])), [0.3, -0.7])


def test_pd_law_and_saturation():
    c = controller()
    assert np.allclose(c.torque(np.array([0.05, 0.0]), np.zeros(2), np.array([0.0, 1.0])), [5.0, -5.0])
    assert np.allclose(c.torque(np.array([1.0, 1.0]), np.zeros(2), np.zeros(2)), [10.0, 20.0])
    assert np.allclose(c.torque(np.array([-1.0, -1.0]), np.zeros(2), np.zeros(2)), [-10.0, -20.0])


def fixed_base_step(joint, target, gravity):
    e = BipedEnv()
    e.bc.setGravity(0, 0, gravity)
    e.bc.createConstraint(e.robot, -1, -1, -1, p.JOINT_FIXED, [0, 0, 0], [0, 0, 0], [0, 0, 1.0])
    e.bc.resetBasePositionAndOrientation(e.robot, [0, 0, 1.0], [0, 0, 0, 1])
    q_ref = np.zeros(12)
    q_ref[joint] = target
    a = e.controller.action_for(q_ref)
    trace = [e.step(a)[4]["q"][joint] for _ in range(100)]  # 2 s
    e.close()
    return np.array(trace)


STEPS = [(0, 0.3), (1, 0.2), (2, 0.4), (3, -0.6), (4, 0.3), (5, 0.2)]


@pytest.mark.parametrize("joint,target", STEPS)
def test_position_tracking_without_load(joint, target):
    """PD puro, sin gravedad: converge al 2 %, sin oscilacion sostenida ni sobrepaso excesivo."""
    t = fixed_base_step(joint, target, 0.0)
    assert abs(t[-25:].mean() - target) < 0.02 * abs(target)
    assert t[-25:].std() < 0.002
    assert np.abs(t).max() < 1.5 * abs(target)


@pytest.mark.parametrize("joint,target", STEPS)
def test_position_tracking_under_gravity(joint, target):
    """Sin compensacion de gravedad hay caida estatica tau/kp; debe ser pequena y estable."""
    t = fixed_base_step(joint, target, CFG["physics"]["gravity"])
    assert abs(t[-25:].mean() - target) < 0.03
    assert t[-25:].std() < 0.005


def test_pd_stable_on_low_inertia_joints_at_home(env):
    """Regresion: con kd=1 en tobillo roll el PD discreto saturaba 20 N m en 5 pasos."""
    a = env.controller.action_for(np.zeros(12))
    env.reset()
    peak = max(env.step(a)[4]["peak_torque"] for _ in range(20))
    assert peak < 15


# ---- Fase 4: observaciones ----

def raw(**kw):
    r = {"q": np.zeros(12), "qd": np.zeros(12), "pos": np.array([0, 0, 0.77]), "euler": np.zeros(3),
         "lin_vel": np.zeros(3), "ang_vel": np.zeros(3), "foot_forces": [0.0, 0.0]}
    r.update(kw)
    return r


def test_observation_layout_and_order():
    q, qd = np.arange(12) * 0.1, np.arange(12) * 0.5
    o = build_observation(raw(q=q, qd=qd, pos=np.array([0, 0, 0.385]), euler=np.array([.1, .2, .3]), lin_vel=np.array([1., 2, 3]),
                              ang_vel=np.array([4., 5, 6]), foot_forces=[150.0, 75.0]), CFG)
    assert o.shape == (OBS_DIM,) and o.dtype == np.float32 and len(NAMES) == OBS_DIM
    assert np.allclose(o[:12], q) and np.allclose(o[12:24], qd)
    assert o[24] == pytest.approx(-0.5)
    assert np.allclose(o[25:28], [.1, .2, .3]) and np.allclose(o[28:31], [1, 2, 3]) and np.allclose(o[31:34], [4, 5, 6])
    assert np.allclose(o[34:36], [0.5, 0.25])


def test_observation_clips():
    o = build_observation(raw(q=np.full(12, 9.), qd=np.full(12, -99.), lin_vel=np.full(3, 50.), ang_vel=np.full(3, -50.),
                              foot_forces=[900.0, -1.0]), CFG)
    assert np.allclose(o[:12], np.pi) and np.allclose(o[12:24], -20)
    assert np.allclose(o[28:31], 5) and np.allclose(o[31:34], -10) and np.allclose(o[34:36], [1, 0])


@pytest.mark.parametrize("bad", [np.nan, np.inf])
def test_observation_rejects_non_finite(bad):
    with pytest.raises(FloatingPointError):
        build_observation(raw(euler=np.array([bad, 0, 0])), CFG)


def test_standing_force_observation_is_physical(env):
    """De pie cada pie lleva media masa: 75 N / 300 N = 0.25. El original observaba ~0.06 (H3)."""
    a = env.controller.action_for(np.zeros(12))
    env.reset()
    vals = [env.step(a)[0][34:36].sum() for _ in range(25)][10:]
    assert np.mean(vals) == pytest.approx(MASS * G / 300, rel=0.05)


def test_euler_signs_and_world_frame(env):
    """Convencion verificada, no asumida: pitch positivo inclina hacia +x; las velocidades estan en marco mundo."""
    q = p.getQuaternionFromEuler([0, 0.3, 0])
    env.bc.resetBasePositionAndOrientation(env.robot, [0, 0, 1], q)
    env.bc.resetBaseVelocity(env.robot, [1, 0, 0], [0, 0, 0])
    r = env.read_state()
    assert r["euler"][1] == pytest.approx(0.3, abs=1e-6)
    assert r["lin_vel"][0] == pytest.approx(1.0) and r["lin_vel"][2] == pytest.approx(0.0, abs=1e-9)
    top = np.array(p.getMatrixFromQuaternion(q)).reshape(3, 3) @ [0, 0, 1]
    assert top[0] > 0


def test_observation_stats():
    s = ObservationStats()
    for v in (1.0, 3.0):
        s.update(np.full(OBS_DIM, v))
    out = s.summary()["roll"]
    assert (out["min"], out["max"], out["mean"]) == (1, 3, 2) and out["std"] == pytest.approx(np.sqrt(2))


# ---- Recompensa ----

def test_curriculum_phases_and_ramp():
    lo, hi = CFG["reward"]["phase_bounds"]
    assert phase_weights(0, CFG) == (CFG["reward"]["phases"][0], 1)
    w, ph = phase_weights((lo + hi) // 2, CFG)
    assert ph == 2 and w["w_vel"] == pytest.approx(1.0)
    assert phase_weights(hi, CFG) == (CFG["reward"]["phases"][2], 3)


def test_reward_matches_equation():
    w = CFG["reward"]["phases"][2]
    # 2*1 + 1.5*1 + 2 - 0.1*1 - 0.3*0.1 - 0.3*0.2
    assert compute_reward(w, 1.0, 0.77, 0.1, -0.2, 1.0, False, CFG) == pytest.approx(5.31)


def test_reward_backward_penalty_clip_and_fall():
    w = CFG["reward"]["phases"][2]
    base = compute_reward(w, 0.0, 0.77, 0, 0, 0, False, CFG)
    assert compute_reward(w, -1.0, 0.77, 0, 0, 0, False, CFG) - base == pytest.approx(-4.0)
    assert compute_reward(w, 9.0, 0.77, 0, 0, 0, False, CFG) - base == pytest.approx(3.0)
    assert compute_reward(w, 0.0, 0.77, 0, 0, 0, True, CFG) - base == pytest.approx(-50.0)
