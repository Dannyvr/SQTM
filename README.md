# Systolic Quantum Teleportation Memory (SQTM)

**Authors:** Danny Valerio-Ramírez (CENFOTEC) · Santiago Núñez-Corrales (UIUC)

Quantum memory architecture based on systolic teleportation to mitigate decoherence in the NISQ era.

---

## Project Structure

```
SQTM/
├── src/                       # Source code (modular quantum circuits)
│   ├── __init__.py
│   ├── modular_circuits/      # Core circuit components (registers, operations)
│   │   ├── __init__.py
│   │   ├── register.py                  # StorageRegister (passive memory tier)
│   │   └── operation_register.py        # OperationRegister (active CPU workspace)
│   └── functions/             # Quantum algorithms & operations (non-components)
│       ├── __init__.py
│       ├── teleportation.py             # SystolicTeleportation (3-parallel bus)
│       └── work_phase.py                # SystolicWorkPhase (NISQ-level SWAP decomposition)
├── tests/                     # Independent test suite (standalone format)
│   ├── __init__.py
│   ├── teleportation_test.py            # End-to-end teleportation simulation (N=3 qubits)
│   └── work_phase_test.py               # Work phase simulation (N=2 qubits)
├── Contexto/                  # Project documentation & research papers
│   ├── SQTM_Paper.md
│   ├── Systolic_Quantum_Teleportation_Memory.txt
│   └── Literatura/            # References & citations
├── data/                      # Calibration data from IBM backends (JSON)
├── results/                   # Simulation outputs, figures, metrics (CSV/PNG)
├── .vscode/                   # VS Code debugging configuration
│   ├── launch.json            # Debug configurations (Main, Tests, Teleportation)
│   ├── settings.json          # Editor & Pylance settings
│   └── extensions.json        # Recommended extensions
├── .venv/                     # Python 3.11 virtual environment (not tracked)
├── pyrightconfig.json         # Pylance type-checking config
├── requirements.txt           # Pinned dependencies
├── main.py                    # Integration test suite (basic module validation)
└── README.md                  # This file
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

### 3. Run Tests

#### **Teleportation Simulation Test**
End-to-end test of the systolic teleportation bus with 3 qubits:
```powershell
python tests/teleportation_test.py
```
**What it does:**
- Creates two `StorageRegister` instances (source and destination, N=3 qubits each)
- Prepares Bell states: X gate on qubit 0 (|1⟩), H gate on qubit 1 (|+⟩)
- Applies `SystolicTeleportation` with 3 parallel channels
- Measures destination register and runs 1024 shots
- Outputs circuit diagram and measurement statistics

#### **Work Phase Simulation Test**
Test of the data bus work phase module with asymmetric state:
```powershell
python tests/work_phase_test.py
```
**What it does:**
- Creates `StorageRegister` (ID: "A") and `OperationRegister` (ID: "1"), each N=2 qubits
- Prepares asymmetric state: X on Storage[0] (|01⟩), X on Operation[1] (|10⟩)
- Applies `SystolicWorkPhase` with SWAP coupling between tiers
- Measures both registers into separate classical registers
- Runs 1024 shots and outputs results
- Expected outcome: 100% correlation `01 10` (entanglement preserved)

#### **Basic Module Test**
Validation of core Register classes:
```powershell
python main.py
```
**What it does:**
- Validates `StorageRegister` instantiation and building
- Validates `OperationRegister` instantiation and building
- Outputs basic integration test results

## Implemented Modules

### Core Quantum Circuits

| Module | Class | Purpose | Status |
|--------|-------|---------|--------|
| `register.py` | `StorageRegister` | Passive memory tier (N qubits) | ✅ Complete |
| `operation_register.py` | `OperationRegister` | Active CPU workspace (Q_1, Q_2, Q_ALU) | ✅ Complete |
| `teleportation.py` | `SystolicTeleportation` | 3-parallel teleportation bus | ✅ Complete |
| `work_phase.py` | `SystolicWorkPhase` | NISQ-level data bus (3 CNOT per qubit) | ✅ Complete |

### Test Suite

| Module | Function | Purpose | Status |
|--------|----------|---------|--------|
| `tests/teleportation_test.py` | `run_teleportation_simulation()` | End-to-end teleportation (N=3, 1024 shots) | ✅ Complete |
| `tests/work_phase_test.py` | `run_work_phase_simulation()` | Work phase simulation (N=2, asymmetric state) | ✅ Complete |

### Architecture Overview

```
┌────────────────────────────────────────────────────┐
│  SQTM — Systolic Quantum Teleportation Memory      │
├────────────────────────────────────────────────────┤
│                                                    │
│  Storage Tier (Passive):                           │
│  ├─ R_A: StorageRegister(3 qubits)                │
│  └─ R_B: StorageRegister(3 qubits)                │
│                                                    │
│  Data Bus (Work Phase):                            │
│  └─ SystolicWorkPhase: 3 CNOT/qubit (NISQ)        │
│     Latency: 9 time steps (N=3)                    │
│                                                    │
│  Operation Tier (Active CPU):                      │
│  ├─ Q_1: OperationRegister(2 qubits)              │
│  ├─ Q_2: OperationRegister(3 qubits)              │
│  └─ Q_ALU: OperationRegister(4 qubits)            │
│                                                    │
│  Teleportation Bus (Systolic):                     │
│  └─ SystolicTeleportation: 3 parallel channels     │
│     Supports deterministic state transfer          │
│                                                    │
└────────────────────────────────────────────────────┘
```

---

## Test Output Interpretation

### Teleportation Test Output
```
[TELEPORTATION CIRCUIT]
... (circuit diagram)

[2] Adding measurement of destination register...
    - Classical register: cr_result (3 bits)
    - Total circuit size: 6 qubits, 3 classical bits

[3] Simulating circuit on AerSimulator (1024 shots)...

[4] Measurement Results:
    - Total shots: 1024
    - Unique outcomes: 1-8 (depends on Bell state preparation)
      010: 512 (50.00%)
      110: 512 (50.00%)
    ...

✓ Teleportation simulation completed successfully
```

**Interpretation:**
- Input state |1+⟩ = (|1⟩ + i|1⟩)/√2 teleports to destination
- Results should reflect the prepared Bell state distribution
- Multiple outcomes = superposition transferred successfully

### Work Phase Test Output
```
[1] Creating Storage Register A and Operation Register 1...
    - Storage Register: reg_A (2 qubits)
    - Operation Register: reg_1 (2 qubits)

[2] Preparing asymmetric initial state...
    - Storage: X → |01⟩
    - Operation: X → |10⟩

[3] Applying SystolicWorkPhase with SWAP coupling...

[4] Measurement Results:
    cr_storage (Storage Register):  01: 1024 (100.00%)
    cr_operation (Operation Register): 10: 1024 (100.00%)

✓ Work phase simulation completed successfully
```

**Interpretation:**
- 100% correlation indicates SWAP preserved entanglement
- Classical bits maintain their prepared state structure
- No leakage or cross-tier information loss

---

## Development Phases

| Phase | Focus | Status |
|-------|-------|--------|
| **0 — Environment** | venv, dependencies, project structure | ✅ Done |
| **A — Building Blocks** | StorageRegister, OperationRegister, Teleportation Bus, Work Phase | ✅ Done |
| **B — Noise Model** | T1/T2 from IBM real backends via `qiskit-ibm-runtime` | 🔲 Next |
| **C — Benchmark** | Fidelity comparison: static memory vs SQTM | 🔲 Pending |
| **D — Real Hardware** | Execution on `ibm_kyiv` / `ibm_brisbane` | 🔲 Pending |
