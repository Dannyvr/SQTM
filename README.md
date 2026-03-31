# Systolic Quantum Teleportation Memory (SQTM)

**Authors:** Danny Valerio-Ramírez (CENFOTEC) · Santiago Núñez-Corrales (UIUC)

Quantum memory architecture based on systolic teleportation to mitigate decoherence in the NISQ era.

---

## Project Structure

```
SQTM/
├── src/                    # Source code (implemented phase by phase)
│   └── __init__.py
├── tests/                  # Unit & integration tests (pytest)
├── data/                   # Calibration data from IBM backends (JSON)
├── results/                # Simulation outputs, figures, metrics (CSV/PNG)
├── .venv/                  # Python 3.11 virtual environment (not tracked)
├── requirements.txt        # Pinned dependencies
└── README.md               # This file
```

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `qiskit` | 1.4.2 | Core SDK: circuits, transpiler, primitives |
| `qiskit-aer` | 0.15.1 | High-performance noisy simulation (T1/T2) |
| `qiskit-ibm-runtime` | 0.34.0 | IBM backend access & calibration data |
| `numpy` | 1.26.4 | N-dimensional arrays & linear algebra |
| `scipy` | 1.13.1 | Advanced math: linalg, stats, optimize |
| `matplotlib` | 3.9.2 | Plots, histograms, fidelity curves |
| `pylatexenc` | 2.10 | LaTeX-style circuit rendering in Qiskit |

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

---

## Development Phases

| Phase | Focus | Status |
|-------|-------|--------|
| **0 — Environment** | venv, dependencies, project structure | ✅ Done |
| **A — Building Blocks** | Deterministic teleportation, systolic registers, QPC | 🔲 Next |
| **B — Noise Model** | T1/T2 from IBM real backends via `qiskit-ibm-runtime` | 🔲 Pending |
| **C — Benchmark** | Fidelity comparison: static memory vs SQTM | 🔲 Pending |
| **D — Real Hardware** | Execution on `ibm_kyiv` / `ibm_brisbane` | 🔲 Pending |
