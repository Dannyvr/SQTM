import sys
import os

from src.modular_circuits.memory_register import StorageRegister
from src.modular_circuits.operation_register import OperationRegister
from src.modular_circuits.qpc import QPC
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

    print("\n QPC Module")
    print("-" * 70)

    qpc = QPC(logical_size=2, c_max=10, t_max=5.0)
    # 1. Hacemos algo (ej. esperar o aplicar un SWAP)
    qpc.update_odometer(logical_address=0, gate_cost=3, time_dt=150.0)

    # 2. El Odómetro nos avisa con un solo llamado unificado
    if qpc.update_odometer(logical_address=0, gate_cost=6, time_dt=2.0) == True:
        print("¡Límite térmico alcanzado! Teletransportando...")
        # Llamamos a teletransportación 1 SOLA VEZ
       
        # Reseteamos los costos y cambiamos de búfer
        qpc.tick(logical_address=0)
    print("=" * 70)

if __name__ == "__main__":
    main()

