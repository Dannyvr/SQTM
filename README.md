# Systolic Quantum Teleportation Memory (SQTM)

**Authors:** Danny Valerio-Ramírez (CENFOTEC) · Santiago Núñez-Corrales (UIUC)

Quantum memory architecture based on systolic teleportation to mitigate decoherence in the NISQ era. Includes comparative analysis with SWAP-based baseline.

---

## Project Structure

```
SQTM/
├── src/                       # Source code (compilers & quantum circuits)
│   ├── __init__.py
│   ├── comparison.py                     # Comparative analysis (SQTM vs SWAP)
│   ├── modular_circuits/                 # Core circuit components
│   │   ├── __init__.py
│   │   ├── qpc.py                        # BipartiteQPC (memory register abstraction)
│   │   ├── memory_register.py            # StorageRegister (passive memory)
│   │   └── operation_register.py         # OperationRegister (active CPU)
│   ├── functions/                        # Quantum algorithms & operations
│   │   ├── __init__.py
│   │   ├── qubit_mapper.py               # Hardware-aware qubit allocation
│   │   ├── teleportation.py              # SystolicTeleportation (3-parallel bus)
│   │   ├── work_phase.py                 # SystolicWorkPhase (NISQ SWAP)
│   ├── simulator/                        # Noisy quantum simulators
│   │   ├── __init__.py
│   │   ├── sqtm_simulator.py             # SQTMCompiler (dual-register memory)
│   │   └── swap_simulator.py             # SwapCompiler (single-register baseline)
│   └── time_calculation/                 # Performance metrics & validation
│       ├── __init__.py
│       ├── tmax_calculator.py            # Passive desgaste threshold
│       ├── cmax_validator.py             # Active desgaste (SQTM)
│       └── cmax_validator_swap.py        # Active desgaste (SWAP)
├── tests/                                # Test suite
│   ├── __init__.py
│   ├── qpc_test.py                       # BipartiteQPC validation
│   ├── teleportation_test.py             # End-to-end teleportation
│   └── work_phase_test.py                # Work phase simulation
├── Contexto/                             # Documentation & research
│   ├── SQTM_Paper.md
│   ├── Systolic_Quantum_Teleportation_Memory.txt
│   └── Literatura/
├── data/                                 # Calibration data
├── results/                              # Simulation outputs
├── test_results/                         # Test execution results
├── .vscode/                              # VS Code configuration
├── .venv/                                # Python 3.11 virtual environment
├── pyrightconfig.json
├── requirements.txt
├── main.py                               # Entry point (parameter configuration)
└── README.md                             # This file
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

### 3. Run Comparative Analysis

**Full SQTM ↔ SWAP comparison:**
```powershell
python main.py
```

**What it does:**
- Loads workload definitions and compiler parameters
- Runs SQTM Compiler (dual-register memory with teleportation)
- Runs SWAP Compiler (single-register baseline)
- Compares fidelity, gate cost, resource usage
- Outputs results to console

**Configuration (edit main.py):**
```python
# Compiler parameters
R = 2          # Number of logical memory registers
n = 2          # Qubits per register
c_max = 100    # Gate cost threshold
t_max_ns = 50000  # Time threshold (nanoseconds)
shots = 256    # Simulation shots per workload

# Workload definitions (list of READ/WRITE/IDLE instructions)
workload1 = ["WRITE", "READ", "WRITE", "READ"]
workload2 = ["WRITE", "READ", "WRITE", "READ", "READ", "IDLE"]
```

### 4. Run Individual Tests

#### **Teleportation Test**
```powershell
python tests/teleportation_test.py
```
Tests the systolic teleportation bus with Bell state preparation.

#### **Work Phase Test**
```powershell
python tests/work_phase_test.py
```
Tests the NISQ-level SWAP decomposition with asymmetric states.

#### **BipartiteQPC Test**
```powershell
python tests/qpc_test.py
```
Validates the quantum processor component abstraction.

---

## Module Reference

### Core Simulators

| Module | Class | Purpose |
|--------|-------|---------|
| `sqtm_simulator.py` | `SQTMCompiler` | Dual-register + teleportation + noise |
| `swap_simulator.py` | `SwapCompiler` | Single-register baseline + SWAP gates |
| `comparison.py` | `run_full_comparison()` | Orchestrate SQTM ↔ SWAP analysis |

### Hardware Mapping

| Module | Class | Purpose |
|--------|-------|---------|
| `qubit_mapper.py` | `QubitMapper` | FakeKyiv backend + chain topology allocation |
| `cmax_validator.py` | `CmaxValidator` | Active desgaste threshold (SQTM) |
| `cmax_validator_swap.py` | `CmaxValidatorSwap` | Active desgaste threshold (SWAP) |
| `tmax_calculator.py` | `TmaxCalculator` | Passive desgaste from T1/T2 times |

### Quantum Circuits

| Module | Class | Purpose |
|--------|-------|---------|
| `memory_register.py` | `StorageRegister` | Passive memory qubits |
| `operation_register.py` | `OperationRegister` | Active operation workspace |
| `qpc.py` | `BipartiteQPC` | Quantum processor component abstraction |
| `teleportation.py` | `SystolicTeleportation` | 3-parallel teleportation bus |
| `work_phase.py` | `SystolicWorkPhase` | NISQ-level SWAP (3 CNOT/qubit) |

---

## Architecture Overview

### SQTM Compiler (Dual-Register Memory)

```
Workload: [WRITE, READ, IDLE, ...] ──→ Parser
                                          ↓
                            QubitMapper (FakeKyiv)
                                          ↓
                    ┌─────────────────────────────────┐
                    │ Chain Topology Allocation:      │
                    │ OpReg → Mem_0 → Ancilla_0 →   │
                    │ Mem_Backup_0 → Mem_1 → ...    │
                    └─────────────────────────────────┘
                                          ↓
                    SystolicTeleportation (3-parallel)
                    + SystolicWorkPhase (NISQ SWAP)
                                          ↓
                    FakeKyiv Backend (127 qubits)
                    + T1/T2 Thermal Relaxation
                                          ↓
                          Fidelity Measurement
```

### SWAP Compiler (Baseline Comparison)

```
Workload: [WRITE, READ, IDLE, ...] ──→ Parser
                                          ↓
                            QubitMapper (FakeKyiv)
                                          ↓
                    ┌─────────────────────────────────┐
                    │ Chain Topology Allocation:      │
                    │ OpReg → Mem_0 → Mem_1 →       │
                    │ Mem_2 → ...                     │
                    └─────────────────────────────────┘
                                          ↓
                    SystolicWorkPhase (NISQ SWAP only)
                                          ↓
                    FakeKyiv Backend (127 qubits)
                    + T1/T2 Thermal Relaxation
                                          ↓
                          Fidelity Measurement
```

### Key Difference
- **SQTM:** 2*R + 1 qubits (memory with backup + operation register)
- **SWAP:** R + 1 qubits (simple baseline)
- **Fair comparison:** Same noise model, backend, seed initialization

---

## Test Output Interpretation

### Comparative Analysis Output
```bash
$ python main.py

======================================================================
SQTM Compiler - Dual-Register Memory with Quantum Teleportation
Target state: |0⟩
======================================================================

[Workload 1] Compilation Phase
  Qubits: 5
  Depth: 42
  Size: 28

[SQTM Results]
  Fidelity: 0.8532
  Total Shots: 256
  Top 5 outcomes:
    |00000⟩: 218 shots
    |10000⟩: 38 shots
    ...

======================================================================
SWAP Compiler - Single-Register Memory (Baseline)
Target state: |0⟩
======================================================================

[Workload 1] Compilation Phase
  Qubits: 3
  Depth: 28
  Size: 16

[SWAP Results]
  Fidelity: 0.7821
  Total Shots: 256
  Top 5 outcomes:
    |000⟩: 200 shots
    |010⟩: 56 shots
    ...

[Comparative Analysis - Workload 1]
+─────────────────────────┬─────────┬─────────+
│ Metric                  │ SQTM    │ SWAP    │
├─────────────────────────┼─────────┼─────────┤
│ Fidelity                │ 85.32%  │ 78.21%  │
│ Qubits                  │ 5       │ 3       │
│ Depth                   │ 42      │ 28      │
│ Gate count              │ 28      │ 16      │
│ Improvement             │ +7.11pp │ baseline│
└─────────────────────────┴─────────┴─────────┘
```

### Output Interpretation
- **Fidelity:** Quantum state preservation quality (higher = better)
- **Gate count:** Total quantum operations (correlates with decoherence)
- **Depth:** Circuit timeline length (deeper = more errors accumulate)
- **pp = percentage points:** Absolute difference in fidelity

### Single Test Outputs

**Teleportation Test** — Bell state distribution after 1024 shots (should show 2-4 outcomes)
```
[4] Measurement Results:
    - Total shots: 1024
    - Unique outcomes: 2
      010: 512 (50.00%)
      110: 512 (50.00%)
```

**Work Phase Test** — SWAP preservation with asymmetric state (should show 100% correlation)
```
[4] Measurement Results:
    cr_storage (Storage Register):  01: 1024 (100.00%)
    cr_operation (Operation Register): 10: 1024 (100.00%)
```

---

## Code Quality & Maintenance (April 6, 2026)

### Recent Updates
✅ **Comment Cleanup** — Removed outdated, redundant, and contradictory comments
- Eliminated misleading noise model documentation
- Removed debug print statements
- Cleaned up visual separators (~35 lines)
- Kept only essential documentation

✅ **Code Organization** — 8 files reviewed and optimized
- sqtm_simulator.py & swap_simulator.py: Fixed noise model comments
- qubit_mapper.py: Removed commented debug code
- memory_register.py & operation_register.py: Simplified structure
- All files: Ensured accuracy between code and comments

---

## Development Phases

| Phase | Focus | Status |
|-------|-------|--------|
| **0 — Environment** | venv, dependencies, project structure | ✅ Complete |
| **A — Building Blocks** | Registers, teleportation, work phase circuits | ✅ Complete |
| **B — Hardware Mapping** | QubitMapper, chain topology allocation | ✅ Complete |
| **C — Noise Model** | T1/T2 from FakeKyiv, thermal relaxation | ✅ Complete |
| **D — Comparative Analysis** | SQTM ↔ SWAP compiler validation & metrics | ✅ Complete |
| **E — Real Hardware** | Execution on IBM Kyiv/Brisbane (pending quota) | ⏳ Pending |
| **F — Optimization** | ML-based adaptive thresholds, topological improvements | 🔲 Future |
