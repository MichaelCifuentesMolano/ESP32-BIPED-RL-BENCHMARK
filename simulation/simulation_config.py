"""Carga de la configuracion unica del proyecto."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "configurations" / "simulation.yaml"


def load_config(path=DEFAULT):
    with open(path, encoding="utf8") as f:
        return yaml.safe_load(f)
