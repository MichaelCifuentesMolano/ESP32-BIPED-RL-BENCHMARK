"""B03: energia a partir de muestras de un medidor externo y ventanas GPIO del analizador logico.

Limite declarado: el INA226 entrega como minimo un dato cada ~280 us (140 us por canal, sin promediado), en practica
mas lento. No resuelve una inferencia individual de pocos cientos de microsegundos. Por eso la energia por inferencia se
obtiene por diferencia de potencia media entre un tramo activo sostenido y uno en reposo, dividida por la tasa.
"""
import numpy as np


def integrate_energy(t_s, v, i):
    """Energia en joules por trapecios."""
    p = np.asarray(v, float) * np.asarray(i, float)
    t = np.asarray(t_s, float)
    return float(np.sum((p[1:] + p[:-1]) * np.diff(t)) / 2)


def mean_power(t_s, v, i):
    t = np.asarray(t_s, float)
    return integrate_energy(t, v, i) / (t[-1] - t[0])


def energy_per_inference(active, idle, inferences_per_s):
    """active e idle: tuplas (t, v, i) de la placa completa.

    Devuelve potencia de placa, potencia en reposo y energia atribuible a la inferencia. Esta ultima es incremental:
    excluye el consumo base que la placa tendria sin inferir.
    """
    p_on, p_off = mean_power(*active), mean_power(*idle)
    return {"board_power_w": p_on, "idle_power_w": p_off, "attributable_power_w": p_on - p_off,
            "energy_per_cycle_board_j": p_on / inferences_per_s,
            "energy_per_inference_attributable_j": (p_on - p_off) / inferences_per_s,
            "resolution_note": "promedio de tramo sostenido, no medicion de una inferencia individual"}


def ina226_can_resolve(pulse_s, sample_period_s, min_samples=10):
    """Falso cuando el pulso no alcanza min_samples: evita presentar lecturas lentas como alta velocidad."""
    return pulse_s / sample_period_s >= min_samples
