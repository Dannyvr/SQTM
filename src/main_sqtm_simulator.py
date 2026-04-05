# ============================================================
# SQTM Research Project — Main Simulator & Compiler
# Systolic Quantum Teleportation Memory
# Authors: Danny Valerio-Ramírez & Santiago Núñez-Corrales
# Role: Quantum Compiler Architect (Senior)
# ============================================================

from typing import Any, Dict, List, Tuple, Optional
import sys
import os
import numpy as np

# Ensure project root is in path for direct execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, circuit, transpile
from qiskit_ibm_runtime.fake_provider import FakeKyiv, FakeBrisbane
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel

from src.modular_circuits.qpc import QPC
from src.modular_circuits.memory_register import StorageRegister
from src.modular_circuits.operation_register import OperationRegister
from src.functions.work_phase import SystolicWorkPhase
from src.functions.teleportation import SystolicTeleportation


class SQTMCompiler:
    """
    Senior-Level Quantum Compiler for Systolic Quantum Teleportation Memory (SQTM).
    
    Manages:
    - Logical to physical qubit mapping
    - Memory register allocation (Original + Backup)
    - Work phase coordination (SWAP operations)
    - Tele-refresh orchestration (odometer-driven coherence management)
    - Noisy simulation with FakeKyiv backend
    """

    # Constant: SWAP operation duration in nanoseconds (NISQ-level)
    SWAP_TIME_NS = 1350

    def __init__(
        self,
        R: int,
        n: int,
        c_max: int,
        t_max_ns: float,
        backend_name: str = "FakeKyiv",
    ):
        """
        Initialize the SQTM Compiler.

        Parameters
        ----------
        R : int
            Number of logical memory registers (e.g., 4).
        n : int
            Qubit width per register (quantum word size).
        c_max : int
            Maximum active desgaste threshold (gate cost).
        t_max_ns : float
            Maximum passive desgaste threshold (idle time in nanoseconds).
        backend_name : str, optional
            Name of fake backend for compilation. Default is "FakeBrisbane".
        """
        self.R = R
        self.n = n
        self.c_max = c_max
        self.t_max_ns = t_max_ns

        # ──────────────────────────────────────────────────────────
        # 1. Initialize backend and qubit resources
        # ──────────────────────────────────────────────────────────
        
        if backend_name == "FakeKyiv":
            self.backend = FakeKyiv()
        elif backend_name == "FakeBrisbane":
            self.backend = FakeBrisbane()
        else:
            raise ValueError(f"Unsupported backend: {backend_name}. Use 'FakeKyiv' or 'FakeBrisbane'.")

        self.available_qubits: List[int] = list(
            range(self.backend.configuration().n_qubits)
        )
        self.logical_to_physical_map: Dict[Any, int] = {}
        """
        Maps qubit_obj (Qubit) -> physical_qubit_id.
        Stores the allocated physical qubit index for each logical qubit object.
        """

        # ──────────────────────────────────────────────────────────
        # 2. Initialize Storage Registers (2*R total: Original + Backup)
        # ──────────────────────────────────────────────────────────

        self.memory_registers_original: List[StorageRegister] = [
            StorageRegister(n_qubits=n, reg_id=f"mem_orig_{i}") for i in range(R)
        ]

        self.memory_registers_backup: List[StorageRegister] = [
            StorageRegister(n_qubits=n, reg_id=f"mem_backup_{i}") for i in range(R)
        ]

        # ──────────────────────────────────────────────────────────
        # 3. Initialize Operation Register (Work Phase)
        # ──────────────────────────────────────────────────────────

        self.operation_register = OperationRegister(n_qubits=n, reg_id="work")

        # ──────────────────────────────────────────────────────────
        # 4. Initialize QPC (Odometer - Hybrid desgaste tracker)
        # ──────────────────────────────────────────────────────────

        self.qpc = QPC(logical_size=R, c_max=c_max, t_max=t_max_ns)

        # Location map: 'O' = Original, 'B' = Backup
        self.location_map: Dict[int, str] = {i: "O" for i in range(R)}

        # Current counters for active tracking (per register)
        self.current_c: Dict[int, int] = {i: 0 for i in range(R)}
        self.current_t: Dict[int, float] = {i: 0.0 for i in range(R)}

        # ──────────────────────────────────────────────────────────
        # 5. Initialize Functional Modules
        # ──────────────────────────────────────────────────────────

        self.work_phase = SystolicWorkPhase(name="sqtm_work_phase")
        self.teleportation = SystolicTeleportation(name="sqtm_teleportation")

        # Cache for built registers (to avoid rebuilding)
        self._built_registers: Dict[str, QuantumRegister] = {}

        print(f"[SQTM Compiler] Initialized: R={R}, n={n}, c_max={c_max}, t_max={t_max_ns} ns")
        print(f"[Backend] {self.backend.__class__.__name__} with {len(self.available_qubits)} qubits")

    # ──────────────────────────────────────────────────────────────
    # QUBIT ALLOCATION & PHYSICAL MAPPING
    # ──────────────────────────────────────────────────────────────

    def _allocate_physical_qubits(
        self,
        register_type: str,
        logical_addr: int,
        quantum_register: QuantumRegister,
    ) -> None:
        """
        Allocate contiguous physical qubits from the backend for a logical register.

        Parameters
        ----------
        register_type : str
            Type of register ('mem_orig', 'mem_backup', 'opreg', 'ancilla').
        logical_addr : int
            Logical address (for memory registers).
        quantum_register : QuantumRegister
            The Qiskit QuantumRegister to allocate qubits for.

        Raises
        ------
        RuntimeError
            If not enough contiguous qubits are available.
        """
        required_qubits = quantum_register.size

        if len(self.available_qubits) < required_qubits:
            raise RuntimeError(
                f"Not enough qubits available. Need {required_qubits}, "
                f"but only {len(self.available_qubits)} remain."
            )

        # Allocate contiguous block (NISQ devices benefit from spatial locality)
        allocated = self.available_qubits[:required_qubits]
        self.available_qubits = self.available_qubits[required_qubits:]

        # Map the actual qubit objects to physical indices
        for local_idx, physical_qubit in enumerate(allocated):
            qubit_obj = quantum_register[local_idx]
            self.logical_to_physical_map[qubit_obj] = physical_qubit

        print(
            f"[Allocation] {register_type}[{logical_addr}]: "
            f"{quantum_register.name} -> physical qubits {allocated}"
        )

    def _get_initial_layout(self, qc: QuantumCircuit) -> List[int]:
        """
        Build the initial_layout for transpilation based on logical_to_physical_map.

        Parameters
        ----------
        qc : QuantumCircuit
            The quantum circuit whose qubits need to be mapped.

        Returns
        -------
        List[int]
            Mapping of circuit qubit indices to physical qubits.
        """
        initial_layout = []
        for qubit in qc.qubits:
            if qubit in self.logical_to_physical_map:
                initial_layout.append(self.logical_to_physical_map[qubit])
            else:
                raise RuntimeError(f"Qubit {qubit} not physically allocated! Cannot simulate.")
        return initial_layout

    # ──────────────────────────────────────────────────────────────
    # COMPILER MAIN METHOD: COMPILE WORKLOAD
    # ──────────────────────────────────────────────────────────────

    def compile_workload(self, workload: List[str]) -> QuantumCircuit:
        """
        Core compilation engine: Process workload instructions and generate circuit.

        Workload format:
        - "IDLE_X": Idle X nanoseconds
        - "READ_ij": Read from logical register i (binary j = lower bits, i = upper bits)
        - "WRITE_ij": Write to logical register i (binary j format)

        Parameters
        ----------
        workload : List[str]
            List of instruction strings.

        Returns
        -------
        QuantumCircuit
            Compiled quantum circuit ready for simulation/execution.
        """

        # ──────────────────────────────────────────────────────────
        # Phase 0: Build register instances and allocate physical qubits
        # ──────────────────────────────────────────────────────────

        qc = QuantumCircuit()

        # Build and allocate memory registers (Original + Backup)
        for i in range(self.R):
            qr_orig = self.memory_registers_original[i].build()
            qr_backup = self.memory_registers_backup[i].build()
            qc.add_register(qr_orig)
            qc.add_register(qr_backup)
            self._allocate_physical_qubits("mem_orig", i, qr_orig)
            self._allocate_physical_qubits("mem_backup", i, qr_backup)
            self._built_registers[f"mem_orig_{i}"] = qr_orig
            self._built_registers[f"mem_backup_{i}"] = qr_backup

        # Build and allocate operation register
        qr_opreg = self.operation_register.build()
        qc.add_register(qr_opreg)
        self._allocate_physical_qubits("opreg", 0, qr_opreg)
        self._built_registers["opreg"] = qr_opreg

        print(f"\n[Compilation] Starting workload processing: {len(workload)} instructions")

        # ──────────────────────────────────────────────────────────
        # Phase 1: Process workload instructions
        # ──────────────────────────────────────────────────────────

        for instruction in workload:
            print(f"  [Instruction] {instruction}")

            if instruction.startswith("IDLE_"):
                # IDLE instruction: Replace delay with X-X pairs
                # Each pair takes ~70ns and adds active depolarizing noise
                num_pairs = int(instruction.split("_")[1])
                time_ns = num_pairs * 70  # Each X-X pair: ~70ns
                for _ in range(num_pairs):
                    qc.x(qr_opreg)  # First X
                    qc.x(qr_opreg)  # Second X (resets state, adds noise)
                print(f"    -> Added {num_pairs} X-X pairs ({time_ns} ns) to operation register")
                
                # Increment time for all active registers
                for i in range(self.R):
                    self.current_t[i] += time_ns
                for logical_addr in range(self.R):    
                    self._check_and_apply_tele_refresh(qc, logical_addr)
                
            elif instruction.startswith("READ_"):
                # READ instruction: READ_ij where ij is binary address
                address_binary = instruction.split("_")[1]
                logical_addr = int(address_binary, 2)  # Binary to decimal

                if logical_addr >= self.R:
                    raise ValueError(f"Logical address {logical_addr} out of range [0, {self.R - 1}]")

                print(f"    -> READ from Mem[{logical_addr}]")

                # Increment counters
                self.current_c[logical_addr] += 1
                self.current_t[logical_addr] += self.SWAP_TIME_NS

                # Determine source register (Original or Backup)
                if self.location_map[logical_addr] == "O":
                    source_reg = self._built_registers[f"mem_orig_{logical_addr}"]
                else:
                    source_reg = self._built_registers[f"mem_backup_{logical_addr}"]

                # Apply SWAP between source and OpReg
                qc = self.work_phase.apply_swap(qc, source_reg, qr_opreg)

                # Check if odometer threshold exceeded
                self._check_and_apply_tele_refresh(qc, logical_addr)

            elif instruction.startswith("WRITE_"):
                # WRITE instruction: WRITE_ij
                address_binary = instruction.split("_")[1]
                logical_addr = int(address_binary, 2)

                if logical_addr >= self.R:
                    raise ValueError(f"Logical address {logical_addr} out of range [0, {self.R - 1}]")

                print(f"    -> WRITE to Mem[{logical_addr}]")

                # Increment counters
                self.current_c[logical_addr] += 1
                self.current_t[logical_addr] += self.SWAP_TIME_NS

                # Determine destination register
                if self.location_map[logical_addr] == "O":
                    dest_reg = self._built_registers[f"mem_orig_{logical_addr}"]
                else:
                    dest_reg = self._built_registers[f"mem_backup_{logical_addr}"]

                # Apply SWAP between OpReg and destination
                qc = self.work_phase.apply_swap(qc, qr_opreg, dest_reg)


                # Check if odometer threshold exceeded
                self._check_and_apply_tele_refresh(qc, logical_addr)       

            else:
                print(f"  [WARNING] Unknown instruction: {instruction}")
            qc.barrier()  # Prevent inter-SWAP optimization
            print(qc.draw(output="text"))   

        print(f"[Compilation] Workload processing complete")
        return qc

    def _check_and_apply_tele_refresh(self, qc: QuantumCircuit, logical_addr: int) -> None:
        """
        Check if odometer thresholds are exceeded; if so, apply tele-refresh.

        Parameters
        ----------
        qc : QuantumCircuit
            The circuit being built.
        logical_addr : int
            Logical address to check.
        """
        requires_refresh = self.qpc.update_odometer(
            logical_addr,
            gate_cost=1,
            time_dt=self.SWAP_TIME_NS
        )

        if requires_refresh:
            print(f"    [Odometer] Threshold exceeded for Mem[{logical_addr}] -> Tele-refreshing")

            # Determine source and destination registers
            if self.location_map[logical_addr] == "O":
                source_reg = self._built_registers[f"mem_orig_{logical_addr}"]
                dest_reg = self._built_registers[f"mem_backup_{logical_addr}"]
                future_location = "B"
            else:
                source_reg = self._built_registers[f"mem_backup_{logical_addr}"]
                dest_reg = self._built_registers[f"mem_orig_{logical_addr}"]
                future_location = "O"

            # Apply quantum teleportation
            qc = self.teleportation.build_circuit(qc, source_reg, dest_reg)

            # FIX: ¡Interceptar registros ancilla creados dinámicamente y asignarles hardware!
            for qreg in qc.qregs:
                if qreg.name not in self._built_registers:
                    self._allocate_physical_qubits("ancilla", logical_addr, qreg)
                    self._built_registers[qreg.name] = qreg

            # Update location map
            self.location_map[logical_addr] = future_location

            # Reset counters via QPC
            self.qpc.tick(logical_addr)
            self.current_c[logical_addr] = 0
            self.current_t[logical_addr] = 0.0

            print(f"    [Tele-Refresh] Mem[{logical_addr}] now stored in {future_location}")

    # ──────────────────────────────────────────────────────────────
    # SIMULATION WITH NOISE
    # ──────────────────────────────────────────────────────────────

    def run_simulation(self, circuit: QuantumCircuit, shots: int = 1024) -> Dict[str, Any]:
        """
        Transpile circuit and simulate with realistic noise (FakeKyiv).

        Parameters
        ----------
        circuit : QuantumCircuit
            Compiled quantum circuit.
        shots : int, optional
            Number of simulation shots. Default is 1024.

        Returns
        -------
        Dict[str, Any]
            Dictionary with:
            - 'fidelity': Overall fidelity (probability of correct result, float)
            - 'counts': Raw measurement counts (dict)
            - 'total_shots': Total number of shots (int)
            - 'error': Error message if simulation failed (str, optional)
        """

        print(f"\n[Simulation] Preparing circuit for {shots} shots")

        try:
            qc_measured = circuit.copy()
            
            # ALWAYS add a specific register for final fidelity
            cr_final = ClassicalRegister(self.n, name="final_meas")
            qc_measured.add_register(cr_final)

            # Determine target register based on architecture
            logical_addr = 0
            if hasattr(self, 'location_map'): # SQTM Logic
                if self.location_map[logical_addr] == "O":
                    target_reg = self._built_registers[f"mem_orig_{logical_addr}"]
                else:
                    target_reg = self._built_registers[f"mem_backup_{logical_addr}"]
            else: # SWAP only Logic
                target_reg = self._built_registers[f"mem_{logical_addr}"]

            # Measure ONLY the target register into cr_final
            for i in range(self.n):
                qc_measured.measure(target_reg[i], cr_final[i])

            # ------------------------------------------------------------------
            # FIX: Transpilación Termodinámica y Topológica Estricta
            # REEMPLAZANDO DELAYS CON PUERTAS X para ruido despolarizante activo
            # ------------------------------------------------------------------
            print("[Transpile] Translating to hardware topology...")
            
            # 1. Extraer layout antes de transpilación.
            #    Los pares X-X simulan T1/T2 decay mediante ruido activo (no silencio).
            initial_layout = self._get_initial_layout(qc_measured)
            
            # 2. Inicializar el simulador y su modelo de ruido usando Matrix Product State (MPS)
            # MPS permite simular los 127 qubits del backend sin explotar la memoria RAM.
            print("[Noise Model] Extracting noise characteristics...")
            noise_model = NoiseModel.from_backend(self.backend)
            simulator = AerSimulator(noise_model=noise_model, method='matrix_product_state')
            
            # 3. Transpilar hacia el BACKEND REAL (self.backend) para forzar la topología Heavy-Hex.
            # Sin scheduling_method porque usamos X-gates en lugar de Delays (sin conflicto ConstrainedReschedule).
            qc_transpiled = transpile(
                qc_measured,
                backend=self.backend,
                optimization_level=0,
                initial_layout=initial_layout
            )
            
            print(f"[Simulator] Running {shots} shots...")
            job = simulator.run(qc_transpiled, shots=shots)
            result = job.result()
            
            counts = result.get_counts()
            total_counts = sum(counts.values())
            
            # Extract results: The last added classical register is always the first block (leftmost) in Qiskit output
            fidelity_count = 0
            target_state = '0' * self.n
            for outcome, count in counts.items():
                dest_bits = outcome.split()[0]  
                if dest_bits == target_state:
                    fidelity_count += count
            
            fidelity = fidelity_count / total_counts if total_counts > 0 else 0.0

            print(f"\n[Circuit] Generated transpiled circuit:")
            print(f"  Qubits: {qc_transpiled.num_qubits}")
            print(f"  Clbits: {qc_transpiled.num_clbits}")
            print(f"  Depth: {qc_transpiled.depth()}")
            print(f"  Size: {qc_transpiled.size()}")
            #print(qc_transpiled.draw(output="text"))  
            print(f"  Fidelity (|0...0> success): {fidelity:.4f}")
            
            # Show top outcomes
            if counts:
                sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
                print(f"  Top 3 outcomes: {dict(sorted_counts[:3])}")

            return {
                "fidelity": fidelity,
                "counts": counts,
                "total_shots": shots,
            }

        except Exception as e:
            print(f"[ERROR] Simulation failed: {e}")
            import traceback
            traceback.print_exc()
            # Return graceful degradation result
            return {
                "fidelity": 0.0,
                "counts": {},
                "total_shots": shots,
                "error": str(e),
            }

    def get_compiler_state(self) -> Dict:
        """
        Return compiler internal state for debugging/inspection.

        Returns
        -------
        Dict
            State dictionary containing maps, counters, etc.
        """
        return {
            "R": self.R,
            "n": self.n,
            "c_max": self.c_max,
            "t_max_ns": self.t_max_ns,
            "location_map": self.location_map,
            "current_c": self.current_c,
            "current_t": self.current_t,
            "logical_to_physical_map": self.logical_to_physical_map,
            "available_qubits": len(self.available_qubits),
        }


# ============================================================
# MAIN: Test Harness
# ============================================================

def main():
    """
    Main test harness for the SQTM Compiler.
    """

    print("=" * 70)
    print("SQTM Compiler - Quantum Teleportation Memory Architecture")
    print("=" * 70)

    # ──────────────────────────────────────────────────────────
    # Configuration
    # ──────────────────────────────────────────────────────────

    R = 2  # Number of logical memory registers
    n = 1  # Qubits per register (quantum word width)
    c_max = 2  # Gate cost threshold
    t_max_ns = 5000.0  # Time threshold (nanoseconds)

    # ──────────────────────────────────────────────────────────
    # Create compiler
    # ──────────────────────────────────────────────────────────

    compiler = SQTMCompiler(R=R, n=n, c_max=c_max, t_max_ns=t_max_ns, backend_name="FakeBrisbane")

    # ──────────────────────────────────────────────────────────
    # Define workload
    # ──────────────────────────────────────────────────────────


    workload = [
        "READ_00",
        "IDLE_4",
        "IDLE_4",
        "IDLE_6",
        "WRITE_00",
        "IDLE_8",
        "IDLE_10",
        "IDLE_2",
        "IDLE_2",
        "READ_00",
        "IDLE_8",
        "WRITE_00",
    ]

    print(f"\n[Workload] Executing {len(workload)} instructions:")
    for i, instr in enumerate(workload, 1):
        print(f"  {i}. {instr}")

    # ──────────────────────────────────────────────────────────
    # Compile workload
    # ──────────────────────────────────────────────────────────

    circuit = compiler.compile_workload(workload)

    print(f"\n[Circuit] Generated circuit:")
    print(f"  Qubits: {circuit.num_qubits}")
    print(f"  Clbits: {circuit.num_clbits}")
    print(f"  Depth: {circuit.depth()}")
    print(f"  Size: {circuit.size()}")
    

    # ──────────────────────────────────────────────────────────
    # Compiler state
    # ──────────────────────────────────────────────────────────

    state = compiler.get_compiler_state()
    print(f"\n[Compiler State]")
    print(f"  Location Map: {state['location_map']}")
    print(f"  Current C counters: {state['current_c']}")
    print(f"  Current T counters: {state['current_t']}")
    print(f"  Available physical qubits: {state['available_qubits']}")

    # ──────────────────────────────────────────────────────────
    # Run simulation
    # ──────────────────────────────────────────────────────────

    print("\n" + "=" * 70)
    print("SIMULATION PHASE")
    print("=" * 70)

    try:
        results = compiler.run_simulation(circuit, shots=2048)
        
        print(f"\n[Simulation Results]")
        print(f"  Fidelity: {results['fidelity']:.4f}")
        print(f"  Total Shots: {results['total_shots']}")
        print(f"  Sample Counts (first 5): {dict(list(results['counts'].items())[:5])}")

    except Exception as e:
        print(f"[Error] Simulation failed: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 70)
    print("COMPILATION & SIMULATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
