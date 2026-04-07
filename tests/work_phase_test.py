# ============================================================
# SQTM Research Project — Work Phase Simulation Test
# Systolic Quantum Teleportation Memory
# Authors: Danny Valerio-Ramírez & Santiago Núñez-Corrales
# ============================================================

import sys
from pathlib import Path

# Add project root to Python path for direct execution
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import Dict
from qiskit import QuantumCircuit, ClassicalRegister, transpile
from qiskit.circuit import QuantumRegister
from qiskit_aer import AerSimulator

from src.modular_circuits.memory_register import StorageRegister
from src.modular_circuits.operation_register import OperationRegister
from src.functions.work_phase import SystolicWorkPhase


def run_work_phase_simulation(N: int = 2, shots: int = 1024) -> Dict[str, int]:
    """
    Run a work phase simulation with asymmetric state preparation.
    
    Parameters
    ----------
    N : int
        Number of qubits in the storage and operation registers.
    shots : int
        Number of simulation shots.
    
    Returns
    -------
    Dict[str, int]
        Measurement counts from both storage and operation registers.
    """
    
    print("=" * 70)
    print("  Work Phase Simulation Test")
    print("=" * 70)
    
    # ──────────────────────────────────────────────────────────────
    # 1. INSTANTIATE REGISTERS
    # ──────────────────────────────────────────────────────────────
    
    print(f"\n[1] Instantiating Registers (N={N})...")
    
    # Storage Register
    storage_factory = StorageRegister(n_qubits=N, reg_id="A")
    storage_reg = storage_factory.build()
    print(f"    - Storage Register: {storage_reg.name} ({storage_reg.size} qubits)")
    
    # Operation Register
    operation_factory = OperationRegister(n_qubits=N, reg_id="1")
    operation_reg = operation_factory.build()
    print(f"    - Operation Register: {operation_reg.name} ({operation_reg.size} qubits)")
    
    # ──────────────────────────────────────────────────────────────
    # 2. CREATE QUANTUM CIRCUIT
    # ──────────────────────────────────────────────────────────────
    
    qc = QuantumCircuit(storage_reg, operation_reg, name="work_phase_test")
    print(f"\n[2] Created Quantum Circuit with {qc.num_qubits} qubits")
    
    # ──────────────────────────────────────────────────────────────
    # 3. ASYMMETRIC STATE PREPARATION
    # ──────────────────────────────────────────────────────────────
    
    print(f"\n[3] Preparing Asymmetric Initial States...")
    
    qc.x(storage_reg[0])
    print(f"    - Storage Register qubit[0]: X gate → State = |1...>")
    
    qc.x(operation_reg[1])
    print(f"    - Operation Register qubit[1]: X gate → State = |.1..>")
    
    print(f"\n[INITIAL STATE CIRCUIT]")
    print(qc.draw(output="text"))
    
    # ──────────────────────────────────────────────────────────────
    # 4. APPLY WORK PHASE (SWAP COUPLING)
    # ──────────────────────────────────────────────────────────────
    
    print(f"\n[4] Applying Work Phase (Systolic SWAP)...")
    work_phase = SystolicWorkPhase(name="storage_to_operation")
    qc = work_phase.apply_swap(qc, storage_reg, operation_reg)
    
    print(f"    - Work Phase Instance: {work_phase}")
    cnot_count = SystolicWorkPhase.get_cnot_cost(N)
    print(f"    - CNOT gates introduced: {cnot_count} (3 per qubit)")
    
    print(f"\n[CIRCUIT AFTER WORK PHASE]")
    print(qc.draw(output="text"))
    
    # ──────────────────────────────────────────────────────────────
    # 5. ADD MEASUREMENTS FOR BOTH REGISTERS
    # ──────────────────────────────────────────────────────────────
    
    print(f"\n[5] Adding Measurements...")
    
    # Classical register for storage
    cr_storage = ClassicalRegister(N, name="cr_storage")
    qc.add_register(cr_storage)
    qc.measure(storage_reg, cr_storage)
    print(f"    - Storage Classical Register: {cr_storage.name} ({N} bits)")
    
    # Classical register for operation
    cr_operation = ClassicalRegister(N, name="cr_operation")
    qc.add_register(cr_operation)
    qc.measure(operation_reg, cr_operation)
    print(f"    - Operation Classical Register: {cr_operation.name} ({N} bits)")
    
    print(f"\n[FINAL CIRCUIT WITH MEASUREMENTS]")
    print(qc.draw(output="text"))
    
    # ──────────────────────────────────────────────────────────────
    # 6. EXECUTE SIMULATION
    # ──────────────────────────────────────────────────────────────
    
    print(f"\n[6] Executing Simulation on AerSimulator ({shots} shots)...")
    backend = AerSimulator()
    transpiled_qc = transpile(qc, backend)
    
    job = backend.run(transpiled_qc, shots=shots)
    result = job.result()
    counts = result.get_counts()
    
    # ──────────────────────────────────────────────────────────────
    # 7. DISPLAY RESULTS
    # ──────────────────────────────────────────────────────────────
    
    print(f"\n[7] Measurement Results:")
    print(f"    - Total shots: {shots}")
    print(f"    - Unique outcomes: {len(counts)}")
    print(f"    - Classical bit layout: 'cr_operation cr_storage'")
    
    # Sort results by frequency
    sorted_counts = dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))
    
    print(f"\n    Outcomes (sorted by frequency):")
    for bitstring, count in sorted_counts.items():
        percentage = (count / shots) * 100
        print(f"      {bitstring}: {count:4d} ({percentage:6.2f}%)")
    
    # Circuit statistics
    print(f"\n[8] Circuit Statistics:")
    print(f"    - Total qubits: {qc.num_qubits} ({N} storage + {N} operation)")
    print(f"    - Classical bits: {qc.num_clbits} ({N} storage + {N} operation)")
    print(f"    - Circuit depth: {qc.depth()}")
    print(f"    - Total gates: {len(qc)}")
    
    print("\n" + "=" * 70)
    print("✓ Work phase simulation completed successfully")
    print("=" * 70)
    
    return counts


def main():
    """Main test function for work phase simulation."""
    print("\n" + "=" * 70)
    print("  SQTM – Work Phase Simulation Test (Standalone)")
    print("=" * 70)
    
    # Run the simulation
    results = run_work_phase_simulation(N=2, shots=1024)
    
    print(f"\n[FINAL RESULTS]")
    print(f"Measurement outcomes:")
    print(results)
    
    print("\n" + "=" * 70)
    print("[TEST COMPLETED] Work phase test finished successfully")
    print("=" * 70)


if __name__ == "__main__":
    main()
