import sys
import os

from src.modular_circuits.register import StorageRegister
from src.modular_circuits.operation_register import OperationRegister
from qiskit.circuit import QuantumCircuit, QuantumRegister


def main():

    
    print("=" * 70)
    
    print("  SQTM – Storage Register + Operation Register (Modular Setup)")
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
    print("[TEST 2] Operation Register Module (Quantum CPU Workspace)")
    print("=" * 70)
    
    
    qpc = OperationRegister(n_qubits=N, reg_id="1")
    op_reg_1 = qpc.build()
    print(f"Fábrica : {qpc}")
    print(f"Registro: {op_reg_1.name}  |  size={op_reg_1.size}")
        
    print(f"\n[INFO] Operation Register Architecture:")
    print(f"    - Q_1 (Operand Register): {qpc.n_qubits} qubits")

    # ──────────────────────────────────────────────────────────────
    # Summary
    # ──────────────────────────────────────────────────────────────
    qc = QuantumCircuit(source_reg, dest_reg, op_reg_1)

    print(qc.draw(output="text"))
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()

