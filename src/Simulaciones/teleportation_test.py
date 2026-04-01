# ============================================================
# SQTM Research Project — Teleportation Simulation Test
# Systolic Quantum Teleportation Memory
# Authors: Danny Valerio-Ramírez & Santiago Núñez-Corrales
# ============================================================

from typing import Dict
from qiskit import QuantumCircuit, ClassicalRegister, transpile
from qiskit.circuit import QuantumRegister
from qiskit_aer import AerSimulator

from src.modular_circuits.teleportation import SystolicTeleportation


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
