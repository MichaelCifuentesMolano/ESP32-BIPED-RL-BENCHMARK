"""Registro de cada experimento: datos crudos en CSV, metadatos y resumen en JSON."""
import csv
import hashlib
import json
import platform
import time
from pathlib import Path

import numpy as np

from simulation.simulation_config import ROOT


def experiment_id(group, **fields):
    """Identificador estable: mismo grupo y configuracion dan el mismo prefijo."""
    digest = hashlib.sha256(json.dumps(fields, sort_keys=True, default=str).encode()).hexdigest()[:8]
    return f"{group}_{digest}"


class ExperimentLog:
    def __init__(self, group, columns, **meta):
        """meta debe incluir model, platform, precision, seed, repetitions; platform 'virtual' marca datos simulados."""
        for key in ("model", "platform", "precision", "seed", "repetitions"):
            if key not in meta:
                raise ValueError(f"falta {key}")
        self.meta = {"id": experiment_id(group, **meta), "group": group, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                     "python": platform.python_version(), "host": platform.platform(),
                     "measured_on_hardware": meta["platform"] != "virtual", **meta}
        self.dir = ROOT / "results" / group / self.meta["id"]
        self.dir.mkdir(parents=True, exist_ok=True)
        self.file = open(self.dir / "raw.csv", "w", newline="", encoding="utf8")
        self.writer = csv.writer(self.file)
        self.writer.writerow(columns)

    def row(self, *values):
        self.writer.writerow(values)

    def close(self, summary):
        self.file.close()
        (self.dir / "result.json").write_text(json.dumps({**self.meta, "summary": summary}, indent=1, default=float), encoding="utf8")
        return self.dir


def latency_stats(values_us):
    v = np.asarray(values_us, float)
    if v.size == 0:
        return {"n": 0}
    return {"n": int(v.size), "mean": float(v.mean()), "median": float(np.median(v)), "p95": float(np.percentile(v, 95)),
            "p99": float(np.percentile(v, 99)), "max": float(v.max()), "min": float(v.min()), "std": float(v.std())}


def deadline_stats(cycle_us, deadline_us=20000, missed=None):
    """missed: mascara opcional de ciclos sin respuesta, que tambien incumplen."""
    v = np.asarray(cycle_us, float)
    miss = v > deadline_us
    if missed is not None:
        miss = miss | np.asarray(missed, bool)
    runs = np.diff(np.flatnonzero(np.diff(np.r_[0, miss.astype(int), 0])))[::2] if miss.any() else np.array([0])
    return {"cycles": int(v.size), "misses": int(miss.sum()), "met_percent": float(100 * (1 - miss.mean())),
            "max_consecutive_misses": int(runs.max()), "jitter_std_us": float(v.std()), "jitter_p99_p50_us": float(np.percentile(v, 99) - np.median(v))}
