import sys
import os

from src.modular_circuits.register import StorageRegister
from src.modular_circuits.operation_register import OperationRegister
from src.modular_circuits.teleportation import SystolicTeleportation
from src.modular_circuits.work_phase import SystolicWorkPhase
from src.Simulaciones.teleportation_test import run_teleportation_simulation
from qiskit.circuit import QuantumCircuit, QuantumRegister


def main():

    
    print("=" * 70)
    
    print("  SQTM – Storage Register + Systolic Teleportation (Word-level)")
    print("=" * 70)

    # ──────────────────────────────────────────────────────────────
    # Test 1: StorageRegister (Passive Storage)
    # ──────────────────────────────────────────────────────────────
    print("\n[TEST 1] Storage Register Module")
    print("-" * 70)

    N = 3

    ra = StorageRegister(n_qubits=N, reg_id="A")
    source_reg = ra.build()
    print(f"Fábrica : {ra}")
    print(f"Registro: {source_reg.name}  |  size={source_reg.size}")


    rb = StorageRegister(n_qubits=N, reg_id="B")
    dest_reg = rb.build()
    print(f"Fábrica : {rb}")
    print(f"Registro: {dest_reg.name}  |  size={dest_reg.size}")

    # ──────────────────────────────────────────────────────────────
    # Test 2: Operation Register (Active Workspace – CPU Cuántica)
    # ──────────────────────────────────────────────────────────────
    
    print("\n" + "=" * 70)
    print("[TEST 4] Operation Register Module (Quantum CPU Workspace)")
    print("=" * 70)
    
    
    qpc = OperationRegister(n_qubits=N, reg_id="1")
    op_reg_1 = qpc.build()
    print(f"Fábrica : {qpc}")
    print(f"Registro: {op_reg_1.name}  |  size={op_reg_1.size}")
        
    print(f"\n[2] Operation Register Architecture:")
    print(f"    - Q_1 (Operand Register): {qpc.n_qubits} qubits")



    qc = QuantumCircuit(source_reg, dest_reg,op_reg_1)

    print(f"\n[1] Preparing source word in quantum state...")
    print(f"    - Source register (A): {N} qubits")
    print(f"    - Destination register (B): {N} qubits")
    
    # Prepare different initial states for each qubit in the "word"
    qc.x(source_reg[0])      # qubit 0: |+⟩
    qc.x(source_reg[1])      # qubit 1: |1⟩

    
    print(f"    - qubit[0]: |1⟩ (X gate)")
    print(f"    - qubit[1]: |1⟩ (X gate)")

    
    print(qc.draw(output="text"))

    # ──────────────────────────────────────────────────────────────
    # Test 3: SystolicTeleportation (Parallel Register-to-Register)
    # ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("[TEST 3] Systolic Teleportation Module (Quantum Word Teleportation)")
    print("=" * 70)
    

    
    # Apply parallel teleportation
    print(f"\n[3] Applying Systolic Teleportation for all {N} qubits...")
    teleporter = SystolicTeleportation(name="systolic_bus")
    qc = teleporter.build_circuit(qc, source_reg, dest_reg)
    
    print(f"\n[3] Teleportation Bus Configuration:")
    print(f"    - Bus: {teleporter}")
    print(f"    - Internal ancilla register: {N} qubits in 'ancilla_ab'")
    print(f"    - Classical results: {2*N} bits in 'cr_bell'")
    print(f"    - Parallelization: {N} independent teleportation channels")
    print(f"    - Source reset: YES (all {N} qubits)")
    print(f"    - Destination reset: NO (carries teleported data)")
    
    print(f"\n[4] Final Circuit Diagram:")
    print(qc.draw(output="text"))
    
    print(f"\n[5] Circuit Statistics:")
    print(f"    - Number of qubits: {qc.num_qubits} ({2*N} storage + {N} ancilla)")
    print(f"    - Number of classical bits: {qc.num_clbits} ({2*N} for BSM)")
    print(f"    - Circuit depth: {qc.depth()}")
    print(f"    - Total operations: {len(qc)}")
    print(f"    - Parallelism factor: {N} quantum words transferred simultaneously")
    
    # ──────────────────────────────────────────────────────────────
    # Test 4: Teleportation Integration Simulation
    # ──────────────────────────────────────────────────────────────
    
    print("\n" + "=" * 70)
    print("[TEST 4] Teleportation Integration Simulation")
    print("=" * 70)
        
    # Pass circuit and registers to simulation function
    results = run_teleportation_simulation(
        qc=qc,
        source_reg=source_reg,
        dest_reg=dest_reg,
        shots=1024
    )
    
    print(f"\n[RESULTS SUMMARY]")
    print(f"Measurement outcomes from destination register:")
    print(results)
    
    # ──────────────────────────────────────────────────────────────
    # Test 5: Systolic Work Phase (Data Bus – Storage to Operation)
    # ──────────────────────────────────────────────────────────────
    
    print("\n" + "=" * 70)
    print("[TEST 5] Systolic Work Phase (Data Bus Architecture)")
    print("=" * 70)
    
    # Create new quantum circuit for work phase demonstration
    work_circuit = QuantumCircuit(source_reg, op_reg_1, name="work_phase_demo")
    
    # Prepare initial state in storage register
    print(f"\n Initial State Preparation (Storage Register):")
    work_circuit.x(source_reg[0])     # |1⟩
    work_circuit.h(source_reg[1])     # |+⟩
    work_circuit.h(source_reg[2])     # |+⟩

    
    # Apply work phase (SWAP coupling)
    print(f"\n Applying Work Phase (Word-level SWAP):")
    
    work_phase = SystolicWorkPhase(name="storage_to_cpu")
    work_circuit = work_phase.apply_swap(work_circuit, source_reg, op_reg_1)
    
    
    cnot_cost = SystolicWorkPhase.get_cnot_cost(N)
    
    print(f"\nCircuit After Work Phase:")
    print(work_circuit.draw(output="text"))
    

    print(f"    - Gate depth: {work_circuit.depth()}")
    print(f"    - Total CNOT gates: {cnot_cost} (3 per qubit swap)")
    print(f"    - Qubit pairs swapped: {N}")
    print(f"    - Data word latency: {3 * N} time steps (3 CNOTs per qubit)")
    print(f"    - Status: Data from storage fully coupled to CPU workspace (NISQ-compatible)")




if __name__ == "__main__":
    main()

