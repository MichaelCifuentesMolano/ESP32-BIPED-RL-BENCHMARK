"""Fija los hechos del informe de fase 1. Si el URDF cambia, estas pruebas deben fallar."""
import hashlib
import sys
from pathlib import Path

import numpy as np
import pybullet as p
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
import inspect_urdf as iu  # noqa: E402

URDF = ROOT / "robot" / "urdf" / "biped.urdf"
SHA256 = "bec0b7e2aa9444ebf15247446b99a3a6daaa1e251df11196e25241ac16d8d89d"
ORDER = [f"{s}_{j}" for s in "lr" for j in ("hip_yaw", "hip_roll", "hip_pitch", "knee_pitch", "ankle_pitch", "ankle_roll")]


@pytest.fixture(scope="module")
def model():
    return iu.parse_urdf(URDF)


@pytest.fixture(scope="module")
def sim():
    cid = p.connect(p.DIRECT)
    yield cid
    p.disconnect(cid)


def test_urdf_is_unmodified():
    assert hashlib.sha256(URDF.read_bytes()).hexdigest() == SHA256


def test_structure_and_no_external_files(model):
    assert len(model["links"]) == 13 and list(model["joints"]) == ORDER
    assert {j["type"] for j in model["joints"].values()} == {"revolute"}
    assert model["external_files"] == []


def test_total_mass_matches_paper(model):
    assert iu.static_summary(model)["total_mass"] == pytest.approx(iu.PAPER["m_total"])


def test_inertias_are_physical_and_match_solids(model):
    for row in iu.check_inertials(model).values():
        assert row["positive_definite"] and row["triangle_inequality"]
        assert row["max_rel_err_vs_analytic"] is None or row["max_rel_err_vs_analytic"] < 1e-3


def test_solid_inertia_formulas():
    assert iu.solid_inertia({"type": "box", "size": "1 1 1"}, 6.0) == pytest.approx([1, 1, 1])
    assert iu.solid_inertia({"type": "cylinder", "radius": "1", "length": "2"}, 2.0)[2] == pytest.approx(1)


def test_sole_reaches_ground_at_spawn_height(model):
    assert iu.static_summary(model)["hip_to_sole"] == pytest.approx(iu.SPAWN_Z)


def test_dh_axes_agree_but_leg_length_differs(model):
    dh = iu.dh_comparison()
    urdf_axes = [model["joints"][n]["axis"] for n in ORDER[:6]]
    assert np.allclose(dh["axes_z_home"], urdf_axes)
    assert dh["end_home"][2] == pytest.approx(-0.86)  # URDF: -0.77


def test_pybullet_order_limits_and_inertia_flag(sim, model):
    r = iu.pb_load_report(URDF, model)
    assert [j["name"] for j in r["joints"]] == ORDER and r["limits_match_urdf"]
    from_file, default = r["inertia_from_file"]["links"], r["default"]["links"]
    assert from_file["l_thigh"]["inertia_diag"] == pytest.approx([0.031083, 0.031083, 0.002])
    assert default["l_thigh"]["inertia_diag"][2] > 0.003  # sin la bandera, Bullet recalcula
    assert default["l_hip_yaw_link"]["inertia_diag"][0] < 1e-8  # URDF declara 1e-6


def test_knee_flexion_moves_ankle_forward(sim):
    r = iu.pb_kinematic_signs(URDF)
    assert r["l_knee_pitch"]["ankle_frame"][0] > 0.3  # URDF
    assert iu.dh_comparison()["ankle_with_positive_knee_0p5"][0] < 0  # rama arccos del articulo


def test_self_collision_pairs_at_home(sim):
    r = iu.pb_self_collision(URDF)
    assert set(r["exclude_parent"]) == {"base_link/l_thigh", "base_link/r_thigh", "l_foot/l_shank", "r_foot/r_shank"}
    assert r["disabled_default"] == {}


def test_substeps_scale_reported_contact_force(sim):
    weight = iu.PAPER["m_total"] * 9.81
    assert iu.pb_smoke(URDF, 0, "a")["mean_normal_force"] == pytest.approx(weight, rel=0.01)
    assert iu.pb_smoke(URDF, 4, "b")["mean_normal_force"] == pytest.approx(weight / 4, rel=0.01)


def test_original_env_also_scales_force_and_tips_over(sim):
    weight = iu.PAPER["m_total"] * 9.81
    four = iu.pb_smoke(URDF, 4, "a", original_env=True, window=(0.2, 0.5))
    zero = iu.pb_smoke(URDF, 0, "b", original_env=True, window=(0.2, 0.5))
    assert zero["mean_normal_force"] == pytest.approx(weight, rel=0.05)
    assert four["mean_normal_force"] == pytest.approx(weight / 4, rel=0.05)
    assert four["z_end"] < 0.4  # juntas bloqueadas sobre contacto blando: vuelca
