"""Fase 1: inspeccion del URDF del bipedo. Solo lee el modelo; nunca lo modifica.

Uso:  python analysis/inspect_urdf.py [ruta.urdf]
Salida: results/fase1/urdf_inspection.json y results/fase1/tables.md
"""
import hashlib
import json
import platform
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pybullet as p

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URDF = ROOT / "robot" / "urdf" / "biped.urdf"
OUT_DIR = ROOT / "results" / "fase1"

# Valores del articulo (Bipedo.pdf): tabla 2, seccion 6.4 y tabla 1.
PAPER = {"l3": 0.38, "l4": 0.36, "l6": 0.12, "m_thigh": 2.5, "m_shank": 1.8, "m_foot": 0.8,
         "m_pelvis": 5.0, "m_total": 15.26}
# Filas (theta_deg, d, a, alpha_deg) de la tabla 1.
DH_TABLE = [(90, 0, 0, 90), (-90, 0, 0, -90), (0, 0, PAPER["l3"], 0),
            (0, 0, PAPER["l4"], 0), (0, 0, 0, 90), (0, 0, PAPER["l6"], 0)]
SPAWN_Z = 0.77  # comentario del URDF, linea 40


def _floats(text):
    return [float(v) for v in text.split()]


def _origin(node):
    o = node.find("origin") if node is not None else None
    if o is None:
        return [0.0] * 3, [0.0] * 3
    return _floats(o.get("xyz", "0 0 0")), _floats(o.get("rpy", "0 0 0"))


def _geometry(node):
    if node is None:
        return None
    g = node.find("geometry")[0]
    return {"type": g.tag, **g.attrib}


def parse_urdf(path):
    """Extrae enlaces, juntas y referencias externas directamente del XML."""
    root = ET.parse(path).getroot()
    links = {}
    for ln in root.findall("link"):
        ine = ln.find("inertial")
        xyz, rpy = _origin(ine)
        i = ine.find("inertia").attrib
        links[ln.get("name")] = {
            "mass": float(ine.find("mass").get("value")), "com": xyz, "com_rpy": rpy,
            "inertia": {k: float(i[k]) for k in ("ixx", "ixy", "ixz", "iyy", "iyz", "izz")},
            "visual": _geometry(ln.find("visual")), "collision": _geometry(ln.find("collision")),
            "visual_origin": _origin(ln.find("visual"))[0], "collision_origin": _origin(ln.find("collision"))[0],
        }
    joints = {}
    for j in root.findall("joint"):
        lim, dyn = j.find("limit"), j.find("dynamics")
        xyz, rpy = _origin(j)
        joints[j.get("name")] = {
            "type": j.get("type"), "parent": j.find("parent").get("link"), "child": j.find("child").get("link"),
            "xyz": xyz, "rpy": rpy, "axis": _floats(j.find("axis").get("xyz")),
            "lower": float(lim.get("lower")), "upper": float(lim.get("upper")),
            "effort": float(lim.get("effort")), "velocity": float(lim.get("velocity")),
            "damping": float(dyn.get("damping")) if dyn is not None else None,
            "friction": float(dyn.get("friction")) if dyn is not None else None,
        }
    external = sorted({e.get("filename") for e in root.iter() if e.get("filename")})
    tags = sorted({e.tag for e in root.iter()})
    return {"robot": root.get("name"), "links": links, "joints": joints, "external_files": external, "xml_tags": tags}


def solid_inertia(geom, mass):
    """Inercia diagonal de un solido homogeneo; None si la geometria no aplica."""
    if geom is None:
        return None
    if geom["type"] == "box":
        x, y, z = _floats(geom["size"])
        return [mass * (y * y + z * z) / 12, mass * (x * x + z * z) / 12, mass * (x * x + y * y) / 12]
    if geom["type"] == "cylinder":
        r, h = float(geom["radius"]), float(geom["length"])
        side = mass * (3 * r * r + h * h) / 12
        return [side, side, mass * r * r / 2]
    return None


def check_inertials(model):
    rows = {}
    for name, ln in model["links"].items():
        i = ln["inertia"]
        tensor = np.array([[i["ixx"], i["ixy"], i["ixz"]], [i["ixy"], i["iyy"], i["iyz"]], [i["ixz"], i["iyz"], i["izz"]]])
        ev = np.sort(np.linalg.eigvalsh(tensor))
        analytic = solid_inertia(ln["collision"], ln["mass"])
        diag = [i["ixx"], i["iyy"], i["izz"]]
        rows[name] = {
            "positive_definite": bool(ev[0] > 0), "triangle_inequality": bool(ev[0] + ev[1] >= ev[2] - 1e-12),
            "analytic_diag": analytic,
            "max_rel_err_vs_analytic": None if analytic is None else
            float(max(abs(a - b) / b for a, b in zip(diag, analytic))),
        }
    return rows


def chain_offsets(model):
    """Posicion de cada enlace en q=0 (todas las rpy son cero; se verifica)."""
    assert all(not any(j["rpy"]) for j in model["joints"].values()), "hay rpy no nula: usar transformadas completas"
    pos = {"base_link": np.zeros(3)}
    pending = list(model["joints"].values())
    while pending:
        for j in list(pending):
            if j["parent"] in pos:
                pos[j["child"]] = pos[j["parent"]] + j["xyz"]
                pending.remove(j)
    return pos


def static_summary(model):
    pos = chain_offsets(model)
    links = model["links"]
    total = sum(l["mass"] for l in links.values())
    com = sum(links[n]["mass"] * (pos[n] + links[n]["com"]) for n in links) / total
    sole = []
    for n in ("l_foot", "r_foot"):
        c, size = pos[n] + links[n]["collision_origin"], _floats(links[n]["collision"]["size"])
        sole.append({"link": n, "x": [c[0] - size[0] / 2, c[0] + size[0] / 2], "y": [c[1] - size[1] / 2, c[1] + size[1] / 2],
                     "z_bottom": c[2] - size[2] / 2})
    virtual = [n for n, l in links.items() if l["collision"] is None]
    return {
        "n_links": len(links), "n_joints": len(model["joints"]),
        "joint_types": sorted({j["type"] for j in model["joints"].values()}),
        "total_mass": total, "virtual_mass": sum(links[n]["mass"] for n in virtual), "virtual_links": virtual,
        "com_home_base_frame": com.tolist(), "soles": sole, "hip_to_sole": -sole[0]["z_bottom"],
        "com_margin_x": [com[0] - sole[0]["x"][0], sole[0]["x"][1] - com[0]],
        "link_offsets": {k: v.tolist() for k, v in pos.items()},
    }


def dh_transform(theta, d, a, alpha):
    """Ecuacion (2) del articulo."""
    ct, st, ca, sa = np.cos(theta), np.sin(theta), np.cos(alpha), np.sin(alpha)
    return np.array([[ct, -st * ca, st * sa, a * ct], [st, ct * ca, -ct * sa, a * st], [0, sa, ca, d], [0, 0, 0, 1]])


def dh_chain(q):
    frames = [np.eye(4)]
    for (th, d, a, al), qi in zip(DH_TABLE, q):
        frames.append(frames[-1] @ dh_transform(np.radians(th) + qi, d, a, np.radians(al)))
    return frames


def dh_comparison():
    f = dh_chain(np.zeros(6))
    bent = dh_chain([0, 0, 0, 0.5, 0, 0])
    return {
        "axes_z_home": [np.round(fr[:3, 2], 6).tolist() for fr in f[:6]],
        "ankle_home": np.round(f[4][:3, 3], 6).tolist(), "end_home": np.round(f[6][:3, 3], 6).tolist(),
        # La ecuacion (6) usa arccos, cuya rama principal da theta4 >= 0.
        "ankle_with_positive_knee_0p5": np.round(bent[4][:3, 3], 6).tolist(),
    }


# ---------------- Pruebas en PyBullet ----------------

def _fresh(urdf, flags=0, fixed=False, z=SPAWN_Z):
    p.resetSimulation()
    return p.loadURDF(str(urdf), [0, 0, z], useFixedBase=fixed, flags=flags)


def _joint_ids(body):
    return {p.getJointInfo(body, i)[1].decode(): i for i in range(p.getNumJoints(body))}


def _free_motors(body):
    n = p.getNumJoints(body)
    p.setJointMotorControlArray(body, list(range(n)), p.VELOCITY_CONTROL, forces=[0.0] * n)


def pb_load_report(urdf, model):
    out = {}
    for label, flags in (("default", 0), ("inertia_from_file", p.URDF_USE_INERTIA_FROM_FILE)):
        b = _fresh(urdf, flags)
        dyn = {}
        names = {-1: "base_link", **{i: p.getJointInfo(b, i)[12].decode() for i in range(p.getNumJoints(b))}}
        for i, ln in names.items():
            d = p.getDynamicsInfo(b, i)
            dyn[ln] = {"mass": d[0], "inertia_diag": list(d[2]), "lateral_friction": d[1], "local_com": list(d[3])}
        out[label] = {"links": dyn, "total_mass": sum(v["mass"] for v in dyn.values())}
    b = _fresh(urdf, p.URDF_USE_INERTIA_FROM_FILE)
    order = []
    for i in range(p.getNumJoints(b)):
        ji = p.getJointInfo(b, i)
        order.append({"index": i, "name": ji[1].decode(), "type": ji[2], "q_index": ji[3], "u_index": ji[4],
                      "damping": ji[6], "friction": ji[7], "lower": ji[8], "upper": ji[9], "max_force": ji[10],
                      "max_velocity": ji[11], "child_link": ji[12].decode(), "axis": list(ji[13]), "parent_index": ji[16]})
    out["joints"] = order
    urdf_order = list(model["joints"])
    out["order_matches_urdf_file"] = [j["name"] for j in order] == urdf_order
    out["limits_match_urdf"] = all(
        abs(j["lower"] - model["joints"][j["name"]]["lower"]) < 1e-9
        and abs(j["upper"] - model["joints"][j["name"]]["upper"]) < 1e-9
        and abs(j["max_force"] - model["joints"][j["name"]]["effort"]) < 1e-9
        and abs(j["max_velocity"] - model["joints"][j["name"]]["velocity"]) < 1e-9 for j in order)
    return out


def pb_kinematic_signs(urdf):
    """Mueve una junta a la vez en base fija y mide hacia donde va el tobillo o pie."""
    b = _fresh(urdf, fixed=True, z=0.0)
    ids = _joint_ids(b)
    foot = ids["l_ankle_roll"]

    def foot_pos():
        return np.array(p.getLinkState(b, foot, computeForwardKinematics=True)[4])

    home = foot_pos()
    res = {"l_ankle_home": home.tolist()}
    for joint, q in (("l_hip_pitch", 0.5), ("l_hip_roll", 0.3), ("r_hip_roll", 0.3), ("l_knee_pitch", -1.0)):
        p.resetJointState(b, ids[joint], q)
        ref = ids["r_ankle_roll"] if joint.startswith("r_") else foot
        res[joint] = {"q": q, "ankle_frame": list(p.getLinkState(b, ref, computeForwardKinematics=True)[4])}
        p.resetJointState(b, ids[joint], 0.0)
    return res


def pb_self_collision(urdf):
    res = {}
    for label, flags in (("self_collision", p.URDF_USE_SELF_COLLISION),
                         ("exclude_parent", p.URDF_USE_SELF_COLLISION | p.URDF_USE_SELF_COLLISION_EXCLUDE_PARENT),
                         ("disabled_default", 0)):
        b = _fresh(urdf, flags, fixed=True, z=1.0)
        name = {-1: "base_link", **{i: p.getJointInfo(b, i)[12].decode() for i in range(p.getNumJoints(b))}}
        p.performCollisionDetection()
        pairs = {}
        for c in p.getContactPoints(b, b):
            k = "/".join(sorted((name[c[3]], name[c[4]])))
            pairs[k] = min(pairs.get(k, 1.0), c[8])
        res[label] = pairs
    return res


def pb_motor_and_damping(urdf):
    """Mide si la amortiguacion y friccion del URDF actuan, y el efecto del motor por defecto."""
    def spin(damping=None, disable=True, torque=None, link_damping=True, steps=200):
        b = _fresh(urdf, p.URDF_USE_INERTIA_FROM_FILE, fixed=True, z=1.0)
        p.setGravity(0, 0, 0)
        p.setTimeStep(0.001)
        j = _joint_ids(b)["l_hip_yaw"]
        if disable:
            _free_motors(b)
        for i in range(-1, p.getNumJoints(b)):
            if damping is not None and i >= 0:
                p.changeDynamics(b, i, jointDamping=damping)
            if not link_damping:
                p.changeDynamics(b, i, linearDamping=0.0, angularDamping=0.0)
        if torque is None:
            p.resetJointState(b, j, 0.0, 3.0)
        for _ in range(steps):
            if torque is not None:
                p.setJointMotorControl2(b, j, p.TORQUE_CONTROL, force=torque)
            p.stepSimulation()
        q, v = p.getJointState(b, j)[:2]
        return {"q": q, "v": v}

    # Torque pequeno y 50 ms: la junta no alcanza su limite, asi la velocidad final es interpretable.
    return {
        "coast": {"v0_rad_s": 3.0, "t_s": 0.2},
        "urdf_damping_motor_off": spin(),
        "zero_joint_damping_motor_off": spin(damping=0.0),
        "zero_joint_and_link_damping_motor_off": spin(damping=0.0, link_damping=False),
        "default_motor_on": spin(disable=False),
        "torque": {"tau_Nm": 0.2, "t_s": 0.05},
        "torque_motor_off": spin(damping=0.0, torque=0.2, steps=50),
        "torque_motor_on": spin(damping=0.0, torque=0.2, disable=False, steps=50),
    }


def apply_original_env(body, plane):
    """Ajustes que RBIPEDO aplica sobre el URDF en envs/biped_env.py, lineas 105, 131 y 147."""
    p.changeDynamics(plane, -1, lateralFriction=0.6, restitution=0.0)
    ids = _joint_ids(body)
    for joint in ("l_ankle_roll", "r_ankle_roll"):  # el enlace hijo de ankle_roll es el pie
        p.changeDynamics(body, ids[joint], lateralFriction=0.6, restitution=0.0, contactStiffness=1e4, contactDamping=50)
    for joint in ("l_ankle_pitch", "l_ankle_roll", "r_ankle_pitch", "r_ankle_roll"):
        p.changeDynamics(body, ids[joint], jointDamping=3.0)


def pb_smoke(urdf, sub_steps, label, flags=p.URDF_USE_INERTIA_FROM_FILE, original_env=False,
             window=(1.0, 2.0)):
    """Prueba de humo con la configuracion del articulo: sin NaN, contacto correcto, costo de computo."""
    p.resetSimulation()
    p.setGravity(0, 0, -9.81)
    p.setPhysicsEngineParameter(fixedTimeStep=0.001, numSolverIterations=50, numSubSteps=sub_steps)
    plane = p.createMultiBody(0, p.createCollisionShape(p.GEOM_PLANE))
    b = p.loadURDF(str(urdf), [0, 0, SPAWN_Z], flags=flags)
    n = p.getNumJoints(b)
    if original_env:
        apply_original_env(b, plane)
    # Solo prueba de carga: sostiene q=0 con el motor interno; no es el controlador PD de la fase 3.
    p.setJointMotorControlArray(b, list(range(n)), p.POSITION_CONTROL, targetPositions=[0.0] * n,
                                forces=[p.getJointInfo(b, i)[10] for i in range(n)])
    t0 = time.perf_counter()
    forces, zs, finite = [], [], True
    for k in range(2000):
        p.stepSimulation()
        if k % 20 == 19:
            pos, _ = p.getBasePositionAndOrientation(b)
            finite &= bool(np.all(np.isfinite(pos)))
            zs.append(pos[2])
            forces.append(sum(c[9] for c in p.getContactPoints(b, plane)))
    wall = time.perf_counter() - t0
    # Fuerzas muestreadas cada 20 ms; la ventana evita medir despues de un vuelco.
    last = forces[int(window[0] * 50):int(window[1] * 50)]
    return {"label": label, "num_sub_steps": sub_steps, "finite": finite, "z_start": zs[0], "z_end": zs[-1],
            "window_s": list(window), "mean_normal_force": float(np.mean(last)), "std_normal_force": float(np.std(last)),
            "weight_N": 15.26 * 9.81, "physics_steps_per_s": 2000 / wall, "real_time_factor": 2.0 / wall}


def markdown_tables(model, r):
    pbj = {j["name"]: j for j in r["pybullet"]["load"]["joints"]}
    lines = ["| PB idx | Junta | Tipo | Padre | Hijo | Origen xyz (m) | Eje | Inf (rad) | Sup (rad) | Inf (grados) | Sup (grados) | Esfuerzo (N m) | Vel (rad/s) | Amort. | Fricc. |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for n, j in model["joints"].items():
        lines.append(f"| {pbj[n]['index']} | {n} | {j['type']} | {j['parent']} | {j['child']} | {j['xyz']} | {j['axis']} | "
                     f"{j['lower']} | {j['upper']} | {np.degrees(j['lower']):.1f} | {np.degrees(j['upper']):.1f} | "
                     f"{j['effort']} | {j['velocity']} | {j['damping']} | {j['friction']} |")
    lines += ["", "| Enlace | Masa (kg) | CoM xyz (m) | Ixx | Iyy | Izz | Visual | Colision | Err. rel. max vs solido |",
              "|---|---|---|---|---|---|---|---|---|"]
    for n, l in model["links"].items():
        i, e = l["inertia"], r["inertial_checks"][n]["max_rel_err_vs_analytic"]
        g = lambda x: "ninguna" if x is None else " ".join(f"{v}" for v in x.values())
        lines.append(f"| {n} | {l['mass']} | {l['com']} | {i['ixx']} | {i['iyy']} | {i['izz']} | {g(l['visual'])} | "
                     f"{g(l['collision'])} | {'n/a' if e is None else f'{e:.2e}'} |")
    return "\n".join(lines) + "\n"


def main(path=DEFAULT_URDF):
    path = Path(path)
    model = parse_urdf(path)
    r = {
        "urdf": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "size_bytes": path.stat().st_size,
        "robot": model["robot"], "external_files": model["external_files"], "xml_tags": model["xml_tags"],
        "static": static_summary(model), "inertial_checks": check_inertials(model), "dh": dh_comparison(),
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "pybullet_api": p.getAPIVersion(),
                        "platform": platform.platform()},
    }
    p.connect(p.DIRECT)
    r["pybullet"] = {
        "load": pb_load_report(path, model), "kinematic_signs": pb_kinematic_signs(path),
        "self_collision": pb_self_collision(path), "motor_and_damping": pb_motor_and_damping(path),
        "smoke": [pb_smoke(path, 4, "articulo numSubSteps=4"), pb_smoke(path, 0, "numSubSteps=0"),
                  pb_smoke(path, 4, "numSubSteps=4 sin INERTIA_FROM_FILE", flags=0),
                  pb_smoke(path, 4, "entorno RBIPEDO numSubSteps=4", original_env=True, window=(0.2, 0.5)),
                  pb_smoke(path, 0, "entorno RBIPEDO numSubSteps=0", original_env=True, window=(0.2, 0.5))],
    }
    p.disconnect()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "urdf_inspection.json").write_text(json.dumps({"model": model, **r}, indent=2), encoding="utf8")
    (OUT_DIR / "tables.md").write_text(markdown_tables(model, r), encoding="utf8")
    return r


if __name__ == "__main__":
    result = main(*sys.argv[1:2])
    print(json.dumps({k: v for k, v in result.items() if k != "inertial_checks"}, indent=1))
