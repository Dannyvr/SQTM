# Systolic Quantum Teleportation Memory (SQTM)

**Authors:** Danny Valerio-Ramírez (CENFOTEC) · Santiago Núñez-Corrales (UIUC)

Quantum memory architecture based on systolic teleportation to mitigate decoherence in the NISQ era.

---

## Project Structure

```
SQTM/
├── Contexto/               # Research context: paper drafts, phase plans, literature
├── src/                    # Source code (implemented phase by phase)
│   ├── __init__.py
│   ├── phase_a/            # Phase A — Modular building blocks
│   │   ├── __init__.py
│   │   ├── teleportation.py    # Deterministic teleportation module
│   │   ├── register.py         # Systolic register (R, Q, R_ab)
│   │   └── qpc.py              # Quantum Program Counter controller
│   ├── phase_b/            # Phase B — Noise environment setup
│   │   ├── __init__.py
│   │   ├── noise_model.py      # T1/T2 noise model from IBM calibration
│   │   └── simulator.py        # AerSimulator wrapper
│   └── utils/              # Shared utilities
│       ├── __init__.py
│       └── visualization.py    # Circuit drawing & fidelity plots
├── tests/                  # Unit & integration tests (pytest)
│   ├── __init__.py
│   ├── test_teleportation.py
│   ├── test_register.py
│   └── test_noise_model.py
├── notebooks/              # Jupyter exploration notebooks
│   └── 00_env_validation.ipynb
├── data/                   # Calibration data from IBM backends (JSON)
│   └── .gitkeep
├── results/                # Simulation outputs, figures, metrics (CSV/PNG)
│   └── .gitkeep
├── requirements.txt        # Pinned dependencies
├── check_env.py            # Environment validation script
└── README.md               # This file
```

---

## Quick Start

### 1. Create Virtual Environment (Python 3.11)
```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies
```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Validate Environment
```powershell
python check_env.py
```

Expected output: `🟢 ENVIRONMENT OK — Ready for SQTM development.`

---

## Development Phases

| Phase | Focus | Status |
|-------|-------|--------|
| **A** | Modular building blocks (teleportation, registers, QPC) | 🔲 Pending |
| **B** | Noise environment (T1/T2 from IBM real backends) | 🔲 Pending |
| **C** | Benchmark simulation (static vs SQTM fidelity) | 🔲 Pending |
| **D** | Real hardware execution (ibm_kyiv / ibm_brisbane) | 🔲 Pending |
