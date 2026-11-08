"""Bucle HIL (modo B) y lector de identidad del dispositivo.

Si el dispositivo no responde a tiempo, se repite la ultima accion valida y el ciclo cuenta como incumplido.
"""
import time

import numpy as np

from host import protocol as pr
from host.serial_interface import DeviceTimeout

INFO_FIELDS = ("chip_model", "cores", "revision", "cpu_mhz", "flash_kb", "psram_kb", "sram_total_kb", "sram_free_kb",
               "idf_major", "idf_minor", "idf_patch", "model_count")


def read_device_info(link):
    """Pide la identidad real de la placa para registrarla junto a cada experimento."""
    link.seq += 1
    body = pr.REQ_BODY.pack(pr.T_INFO_REQUEST, 0, 0, link.seq, 0, *([0.0] * 36))
    link.t.write(pr.SYNC_REQ + body + pr.struct.pack("<H", pr.crc16(body)))
    end = time.perf_counter() + 1.0
    while time.perf_counter() < end:
        n = link.t.in_waiting
        for f in link.parser.feed(link.t.read(n)) if n else ():
            if f[0] == pr.T_INFO_RESPONSE and f[2] == link.seq:
                return {**dict(zip(INFO_FIELDS, f[5:])), "min_free_heap": f[4]}
    raise DeviceTimeout("sin identidad")


def wait_ready(link, tries=60, pause_s=0.5):
    """Reintenta read_device_info mientras la placa arranca (QEMU o placa recien conectada)."""
    for _ in range(tries):
        try:
            return read_device_info(link)
        except (DeviceTimeout, OSError):
            time.sleep(pause_s)
    raise DeviceTimeout("el firmware no respondio")


def run_episode(env, link, model_id, noise, push=None, on_cycle=None):
    """Un episodio HIL: pasos 1 a 8 del modo B. Devuelve metricas funcionales y temporales por ciclo.

    push: (paso, fuerza_xyz, duracion_s) para B07. on_cycle: funcion para registrar cada ciclo.
    """
    obs = env.reset(noise)
    action = env.controller.action_for(np.zeros(12))
    cycles = []
    total, term, info = 0.0, False, None
    while True:
        t_start = time.perf_counter()
        missed, infer_us, round_us = False, 0, 0.0
        try:
            r = link.infer(obs, model_id)
            if r["status"] == pr.STATUS_OK:
                action = np.asarray(r["actions"])
                infer_us, round_us = r["infer_us"], r["round_trip_us"]
            else:
                missed = True
        except DeviceTimeout:
            missed = True
        if push and env.steps == push[0]:
            env.apply_push(push[1], push[2])
        t_sim = time.perf_counter()
        obs, reward, term, trunc, info = env.step(action)
        t_end = time.perf_counter()
        total += reward
        c = {"infer_us": infer_us, "round_trip_us": round_us, "transfer_us": max(round_us - infer_us, 0.0),
             "host_us": (t_end - t_sim) * 1e6, "control_path_us": (t_sim - t_start) * 1e6, "cycle_us": (t_end - t_start) * 1e6,
             "missed": missed, "x": info["x"], "z": info["z"], "roll": info["roll"], "pitch": info["pitch"],
             "f_left": info["foot_forces"][0], "f_right": info["foot_forces"][1], "energy": info["energy"]}
        cycles.append(c)
        if on_cycle:
            on_cycle(c)
        if term or trunc:
            break
    duration = env.steps * env.ctrl_dt
    return {"return": total, "fallen": bool(term), "duration_s": duration, "distance_m": info["x"], "speed_mps": info["x"] / duration,
            "pitch_rms": float(np.sqrt(np.mean([c["pitch"] ** 2 for c in cycles]))), "roll_rms": float(np.sqrt(np.mean([c["roll"] ** 2 for c in cycles]))),
            "peak_force_n": float(max(max(c["f_left"], c["f_right"]) for c in cycles)), "cycles": cycles}
