import sys
import os

from src.modular_circuits.memory_register import StorageRegister
from src.modular_circuits.operation_register import OperationRegister
from src.modular_circuits.qpc import QPC
from qiskit.circuit import QuantumCircuit, QuantumRegister
from src.main_sqtm_simulator import SQTMCompiler


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

    # ──────────────────────────────────────────────────────────────
    # Test 3: Full SQTM Compiler (Senior Architecture)
    # ──────────────────────────────────────────────────────────────
    
    print("\n\n")
    print("=" * 70)
    print("[TEST 3] SQTM Senior Compiler - Full Integration Test")
    print("=" * 70)
    
    # Configuration for the compiler
    R = 2  # Logical memory registers
    n = 2  # Qubit width per register
    c_max = 100  # Gate cost threshold
    t_max_ns = 50000.0  # Time threshold

    # Create compiler instance
    compiler = SQTMCompiler(R=R, n=n, c_max=c_max, t_max_ns=t_max_ns)

    # Define workload
    workload = [
        "WRITE_00",  # Write to Mem[0]
        "WRITE_01",  # Write to Mem[1]
        "IDLE_3000",  # Idle 3000 ns
        "READ_00",   # Read from Mem[0]
        "IDLE_8000",  # Idle 8000 ns
        "READ_01",   # Read from Mem[1]
    ]

    print(f"\n[Workload Configuration] {len(workload)} instructions")
    for i, instr in enumerate(workload, 1):
        print(f"  {i}. {instr}")

    # Compile the workload
    print("\n[Compiling workload...]")
    circuit = compiler.compile_workload(workload)

    print(f"\n[Circuit Metrics]")
    print(f"  Quantum bits: {circuit.num_qubits}")
    print(f"  Classical bits: {circuit.num_clbits}")
    print(f"  Circuit depth: {circuit.depth()}")
    print(f"  Total operations: {circuit.size()}")

    # Display compiler state
    state = compiler.get_compiler_state()
    print(f"\n[Final Compiler State]")
    print(f"  Logical-to-Physical mapping entries: {len(state['logical_to_physical_map'])}")
    print(f"  Data location (Original/Backup): {state['location_map']}")
    print(f"  Active gate costs: {state['current_c']}")
    print(f"  Idle time accumulation: {state['current_t']}")

    # Run simulation with noise
    print("\n" + "=" * 70)
    print("[SIMULATION] Noisy Execution (FakeKyiv + Noise Model)")
    print("=" * 70)

    try:
        results = compiler.run_simulation(circuit, shots=256)
        
        print(f"\n[Simulation Results]")
        print(f"  Fidelity (correctness probability): {results['fidelity']:.4f}")
        print(f"  Total measurement shots: {results['total_shots']}")
        print(f"  ✓ Simulation completed successfully")

    except Exception as e:
        print(f"  ✗ Simulation error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 70)
    print("[SUMMARY] All tests completed")
    print("=" * 70)

if __name__ == "__main__":
    main()

