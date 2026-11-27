# ESP32-BIPED-RL-BENCHMARK

Reproducible hardware-in-the-loop (HIL) testbed and benchmark for quantized Soft Actor-Critic (SAC) locomotion
policies running on ESP32-class microcontrollers. A 12-DoF 3D biped is simulated in PyBullet on the host; the
policy runs on the board and exchanges observations and actions over UART every 20 ms.

Companion code and data of the paper *"A Reproducible Hardware-in-the-Loop Testbed and Benchmark for Evaluating
Energy Efficiency and Temporal Reliability of Quantized Reinforcement Learning Policies for Biped Locomotion on
MCUs"* (submitted to IEEE LatinIoT 2027).

- Actors: original 36-256-256-12 and compact 36-64-64-12, each in FP32, INT16 and INT8, 3 training seeds.
- Boards: ESP32-WROOM-32 (D0WD-V3) and ESP32-S3 (N16R8), ESP-IDF 5.5.1.
- Benchmarks: B01 inference latency, B02 memory, B03 energy (INA226), B04 long-run stability,
  B05 closed-loop walking under a deadline, B06 push recovery, B07 force sweep.

## Layout

| Path | Content |
|---|---|
| `robot/urdf/` | Biped URDF (see *URDF provenance*) |
| `simulation/`, `reinforcement_learning/` | PyBullet environment and SAC training |
| `models/`, `datasets/` | Trained actors (`best` checkpoints) and observation sets for quantization and parity |
| `firmware/` | ESP-IDF projects: policy server, energy meter (`meter_app`), timing and power monitor |
| `host/` | HIL controller, serial protocol, bit-exact virtual ESP32, QEMU bridge, energy runner |
| `benchmark/`, `analysis/` | B01-B07 runners, reports, logic-analyzer decoding |
| `results/` | Raw data and `result.json` of every run, including on-board measurements |
| `documentation/` | Design notes, quantization format, hardware wiring guide (in Spanish) |
| `tests/` | pytest suite (`python -m pytest -q`) |

## Reproduce

    conda env create -f environment.yml
    conda activate latiniot
    python -m pytest -q
    python -m reinforcement_learning.training.run_matrix --seeds 0 1 2 --steps 3000000
    python -m benchmark.run_all --seeds 0 1 2      # observations, quantization, B05-B07, firmware, QEMU, report

The firmware needs ESP-IDF 5.5.1 in `~/esp/esp-idf`; build with `firmware/build_all.ps1` from PowerShell.
Tables and figures are written to `results/report/`.

Without a board, B05-B07 run on a virtual ESP32 that reproduces the firmware arithmetic bit for bit: walking
performance is valid, device timing is not. B01, B03 and B04 require hardware; wiring and commands for each
measurement are in `documentation/guia_conexion_hardware.md`.

## URDF provenance

`robot/urdf/biped.urdf` is a byte-identical copy of the model in
[RBIPEDO](https://github.com/kevin-ortega2724/RBIPEDO) (commit `d1effbd`) by Kevin David Ortega-Quinones,
redistributed here with the author's permission. `tests/test_urdf_inspection.py` pins its SHA-256.

## License

MIT, see `LICENSE`.
