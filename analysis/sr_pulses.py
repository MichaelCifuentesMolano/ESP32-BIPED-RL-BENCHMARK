"""Anchos de pulso de D0 (GPIO4, inferencia) y D1 (GPIO5, trama) en un .sr de sigrok."""
import sys, zipfile, re, json
import numpy as np
z = zipfile.ZipFile(sys.argv[1])
meta = z.read("metadata").decode()
rate = {"k":1e3,"m":1e6}[re.search(r"samplerate=\d+ (\w)Hz", meta).group(1).lower()] * int(re.search(r"samplerate=(\d+)", meta).group(1))
chunks = sorted((n for n in z.namelist() if n.startswith("logic-1")), key=lambda n: int(n.rsplit("-",1)[1]) if n.count("-")>1 else 0)
x = np.frombuffer(b"".join(z.read(n) for n in chunks), dtype=np.uint8)
def pulses(bit):
    s = ((x >> bit) & 1).astype(np.int8); d = np.diff(s)
    r = np.flatnonzero(d == 1) + 1; f = np.flatnonzero(d == -1) + 1
    f = f[f > r[0]] if len(r) else f
    n = min(len(r), len(f)); return r[:n], f[:n]
out = {"samplerate_hz": rate, "duracion_s": len(x)/rate}
(r0, f0), (r1, f1) = pulses(0), pulses(1)
for name, (r, f) in (("gpio4_inferencia", (r0, f0)), ("gpio5_trama", (r1, f1))):
    w = (f - r) / rate * 1e6
    out[name] = {"n": int(len(w)), "mean_us": float(w.mean()), "median_us": float(np.median(w)), "min_us": float(w.min()), "max_us": float(w.max()), "std_us": float(w.std())} if len(w) else {"n": 0}
# cada pulso de GPIO4 debe caer dentro de un pulso de GPIO5
i = np.searchsorted(r1, r0, side="right") - 1
ok = (i >= 0) & (f0 <= f1[np.clip(i, 0, None)]) if len(r1) else np.zeros(len(r0), bool)
out["gpio4_dentro_de_gpio5"] = f"{int(ok.sum())}/{len(r0)}"
print(json.dumps(out, indent=1))
