# ============================================================
# SQTM Research Project — Teleportation Simulation Test
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
from src.functions.teleportation import SystolicTeleportation


def run_teleportation_simulation(
    qc: QuantumCircuit,
    source_reg: QuantumRegister,
    dest_reg: QuantumRegister,
    shots: int = 1024
) -> Dict[str, int]:
    
    
    N = source_reg.size
    
   
   
    # ──────────────────────────────────────────────────────────────
    # 2. ADD MEASUREMENT OF DESTINATION REGISTER
    # ──────────────────────────────────────────────────────────────
    
    print(f"\n[2] Adding measurement of destination register...")
    cr_result = ClassicalRegister(N, name="cr_result")
    qc.add_register(cr_result)
    qc.measure(dest_reg, cr_result)
    print(f"    - Classical register: {cr_result.name} ({N} bits)")
    print(f"    - Total circuit size: {qc.num_qubits} qubits, {qc.num_clbits} classical bits")
    
    print(qc.draw(output="text"))

    # ──────────────────────────────────────────────────────────────
    # 3. TRANSPILE AND SIMULATE
    # ──────────────────────────────────────────────────────────────
    
    print(f"\n[3] Simulating circuit on AerSimulator ({shots} shots)...")
    backend = AerSimulator()
    t_qc = transpile(qc, backend)
    
    result = backend.run(t_qc, shots=shots).result()
    counts = result.get_counts()
    
    # ──────────────────────────────────────────────────────────────
    # 4. DISPLAY RESULTS
    # ──────────────────────────────────────────────────────────────
    
    print(f"\n[4] Measurement Results:")
    print(f"    - Total shots: {shots}")
    print(f"    - Unique outcomes: {len(counts)}")
    
    # Sort results by frequency for better readability
    sorted_counts = dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))
    
    for bitstring, count in sorted_counts.items():
        percentage = (count / shots) * 100
        print(f"      {bitstring}: {count:4d} ({percentage:6.2f}%)")
    
    print("\n" + "=" * 70)
    print("✓ Teleportation simulation completed successfully")
    print("=" * 70)
    
    return counts


def main():
    """Main test function for teleportation simulation."""
    
    print("=" * 70)
    print("  SQTM – Teleportation Simulation Test")
    print("=" * 70)
    
    # ──────────────────────────────────────────────────────────────
    # Setup: Create Storage Registers
    # ──────────────────────────────────────────────────────────────
    N = 3
    
    print(f"\n[1] Setting up Storage Registers (N={N})...")
    
    # Source register
    ra = StorageRegister(n_qubits=N, reg_id="A")
    source_reg = ra.build()
    print(f"    - Source Register: {source_reg.name} ({source_reg.size} qubits)")
    
    # Destination register
    rb = StorageRegister(n_qubits=N, reg_id="B")
    dest_reg = rb.build()
    print(f"    - Destination Register: {dest_reg.name} ({dest_reg.size} qubits)")
    
    # ──────────────────────────────────────────────────────────────
    # Create Quantum Circuit
    # ──────────────────────────────────────────────────────────────
    qc = QuantumCircuit(source_reg, dest_reg)
    
    # ──────────────────────────────────────────────────────────────
    # Prepare Initial State
    # ──────────────────────────────────────────────────────────────
    print(f"\n[2] Preparing initial quantum state...")
    qc.x(source_reg[0])      # qubit 0: |1⟩
   
    print(f"    - Source qubit[0]: X gate → |1⟩")

    
    print(f"\n[INITIAL CIRCUIT]")
    print(qc.draw(output="text"))
    
    # ──────────────────────────────────────────────────────────────
    # Apply Systolic Teleportation
    # ──────────────────────────────────────────────────────────────
    print(f"\n[3] Applying Systolic Teleportation...")
    teleporter = SystolicTeleportation(name="systolic_bus")
    qc = teleporter.build_circuit(qc, source_reg, dest_reg)
    print(f"    - Teleportation bus: {teleporter}")
    print(f"    - Parallelization: {N} independent channels")
    
    print(f"\n[TELEPORTATION CIRCUIT]")
    print(qc.draw(output="text"))
    
    # ──────────────────────────────────────────────────────────────
    # Run Simulation
    # ──────────────────────────────────────────────────────────────
    print(f"\n[4] Running simulation...")
    results = run_teleportation_simulation(
        qc=qc,
        source_reg=source_reg,
        dest_reg=dest_reg,
        shots=1024
    )
    
    print(f"\n" + "=" * 70)
    print("[TEST COMPLETED] Teleportation test finished successfully")
    print("=" * 70)
    
    return results


if __name__ == "__main__":
    main()
