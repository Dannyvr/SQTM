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
import random

# Ensure project root is in path for direct execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile
from qiskit.circuit import Instruction
from qiskit_ibm_runtime.fake_provider import FakeKyiv
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, thermal_relaxation_error

from src.modular_circuits.memory_register import StorageRegister
from src.modular_circuits.operation_register import OperationRegister
from src.functions.work_phase import SystolicWorkPhase
from src.functions.qubit_mapper import QubitMapper


class SwapCompiler:
    """
    Senior-Level Quantum Compiler for Systolic Quantum Memory (SQM).
    
    Manages:
    - Logical to physical qubit mapping
    - Memory register allocation (Single copy per register)
    - Work phase coordination (SWAP operations)
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
        initial_state: int = 0,
    ):
        """
        Initialize the Swap Compiler.

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
            Name of fake backend for compilation. Default is "FakeKyiv".
        initial_state : int, optional
            Initial quantum state for fidelity calculation: 0 for |0⟩ state, 1 for |1⟩ state. Default is 0.
        """
        self.R = R
        self.n = n
        self.c_max = c_max
        self.t_max_ns = t_max_ns
        self.initial_state = initial_state

        # ──────────────────────────────────────────────────────────
        # 1. Initialize backend and qubit resources
        # ──────────────────────────────────────────────────────────
        
       
        self.backend = FakeKyiv()
        
        # CRITICAL: Use EMPTY noise model instead of backend's calibration
        # Reason: Backend noise includes gate errors, readout errors, etc.
        # We want ONLY thermal relaxation on idle periods for clean comparison
        self.noise_model = NoiseModel.from_backend(self.backend)

        # ──────────────────────────────────────────────────────────
        # 1b. Create thermal relaxation error linked to 'id' gate
        # ──────────────────────────────────────────────────────────
        # T1 and T2 times for FakeKyiv (typical NISQ parameters)
        t1_ns = 150_000  # 150 μs
        t2_ns = 100_000  # 100 μs
        self.time_idle_ns = 70  # One IDLE unit = 70 ns (equivalent to one gate cycle)
        
        # Create thermal relaxation error for the idle period
        idle_error = thermal_relaxation_error(t1_ns, t2_ns, self.time_idle_ns)
        
        # Inject thermal relaxation to 'id' gate (applied during IDLE periods)
        num_physical_qubits = self.backend.configuration().n_qubits
        for q in range(num_physical_qubits):
            self.noise_model.add_quantum_error(idle_error, 'id', [q],warnings=False)
        
        print(f"[Swap Compiler] Thermal relaxation configured: T1={t1_ns/1000:.1f}μs, T2={t2_ns/1000:.1f}μs")
        print(f"[Swap Compiler] Idle period per unit: {self.time_idle_ns} ns")
        print(f"[Swap Compiler] Applied thermal decay to 'id' gate on {num_physical_qubits} qubits")

        # Initialize QubitMapper for intelligent qubit allocation
        self.qubit_mapper = QubitMapper(self.backend)
        
        self.logical_to_physical_map: Dict[Any, int] = {}
        """
        Maps qubit_obj (Qubit) -> physical_qubit_id.
        Stores the allocated physical qubit index for each logical qubit object.
        """
        
        self.qubit_register_map: Dict[int, str] = {}
        """
        Maps physical_qubit_id -> register_name.
        Used for validation and tracking.
        """

        # ──────────────────────────────────────────────────────────
        # 2. Initialize Storage Registers (Single copy per register)
        # ──────────────────────────────────────────────────────────

        self.memory_registers: List[StorageRegister] = [
            StorageRegister(n_qubits=n, reg_id=f"mem_{i}") for i in range(R)
        ]

        # ──────────────────────────────────────────────────────────
        # 3. Initialize Operation Register (Work Phase)
        # ──────────────────────────────────────────────────────────

        self.operation_register = OperationRegister(n_qubits=n, reg_id="work")

        # ──────────────────────────────────────────────────────────
        # 4. Initialize Functional Modules
        # ──────────────────────────────────────────────────────────

        self.work_phase = SystolicWorkPhase(name="sqtm_work_phase")

        # Cache for built registers (to avoid rebuilding)
        self._built_registers: Dict[str, QuantumRegister] = {}

        state_label = "|0⟩" if initial_state == 0 else "|1⟩"
        print(f"[Swap Compiler] Initialized: R={R}, n={n}, c_max={c_max}, t_max={t_max_ns} ns")
        print(f"[Swap Compiler] Fidelity target state: {state_label}")
        print(f"[Backend] {self.backend.__class__.__name__} with {self.qubit_mapper.n_qubits} qubits")

    # ──────────────────────────────────────────────────────────────
    # QUBIT ALLOCATION & PHYSICAL MAPPING (DEPRECATED)
    # ──────────────────────────────────────────────────────────────
    # Note: _allocate_physical_qubits is now handled by QubitMapper.allocate_star_topology()
    # during compile_workload(). Keeping for backwards compatibility if needed.

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
        # SEED INITIALIZATION - For reproducibility
        # ──────────────────────────────────────────────────────────
        random.seed(42)
        np.random.seed(42)

        # ──────────────────────────────────────────────────────────
        # Phase 0: Build register instances and allocate physical qubits
        # CRITICAL: Use chain topology to ensure fair comparison with SQTM
        # ──────────────────────────────────────────────────────────

        qc = QuantumCircuit()

        # Build all register instances (logical) first
        for i in range(self.R):
            qr_mem = self.memory_registers[i].build()
            qc.add_register(qr_mem)
            self._built_registers[f"mem_{i}"] = qr_mem

        qr_opreg = self.operation_register.build()
        qc.add_register(qr_opreg)
        self._built_registers["opreg"] = qr_opreg

        # ──────────────────────────────────────────────────────────
        # CHAIN TOPOLOGY ALLOCATION (SCALABLE LINEAR STRUCTURE)
        # ──────────────────────────────────────────────────────────
        # The registers form a linear chain for minimal routing SWAPs:
        # OpReg — Mem_0 — Mem_1 — ... — Mem_(R-1)
        # This ensures direct connectivity without routing SWAPs with optimization_level=0
        # ──────────────────────────────────────────────────────────
        
        print("\n[Compilation] Allocating chain topology (OpReg—Mem_0—Mem_1—...)...")
        
        # Build chain configuration: OpReg first, then all memory registers
        chain_config = [("opreg", self.n)]  # Operation register as first element
        for i in range(self.R):
            chain_config.append((f"mem_{i}", self.n))
        
        total_qubits_needed = sum(size for _, size in chain_config)
        print(f"[Compilation] Total qubits needed: {total_qubits_needed}")
        
        # Allocate the linear chain
        allocation_map = self.qubit_mapper.allocate_chain_topology(chain_config)
        
        # Map logical qubits to physical qubits for all registers
        for reg_id, physical_qubits in allocation_map.items():
            if reg_id == "opreg":
                qr = self._built_registers["opreg"]
            else:
                # mem_0, mem_1, ...
                qr = self._built_registers[reg_id]
            
            for local_idx, physical_qubit in enumerate(physical_qubits):
                qubit_obj = qr[local_idx]
                self.logical_to_physical_map[qubit_obj] = physical_qubit
                self.qubit_register_map[physical_qubit] = reg_id

        print(f"[Compilation] Physical qubit mapping:")
        for reg_id, phys_qubits in allocation_map.items():
            print(f"  {reg_id:12s} → {sorted(phys_qubits)}")

        print(f"\n[Compilation] Total qubits allocated: {len(self.logical_to_physical_map)}")

        # ──────────────────────────────────────────────────────────
        # Phase 0b: Prepare initial quantum state
        # ──────────────────────────────────────────────────────────
        
        if self.initial_state == 1:
            print("\n[Compilation] Preparing initial state |1...1⟩ (applying X to all qubits: memory + operation register)...")
            # Apply X gates to ALL qubits (memory and operation register) to prepare |1...1⟩ state
            # This ensures SWAPs don't affect the final state validation
            
            # Apply X to operation register
            for qubit in qr_opreg:
                qc.x(qubit)
            
            # Apply X to all memory qubits
            for i in range(self.R):
                qr_mem = self._built_registers[f"mem_{i}"]
                # Apply X to memory
                for qubit in qr_mem:
                    qc.x(qubit)
            
            qc.barrier()
            print("[Compilation] Initial state |1...1⟩ prepared for all qubits")
        else:
            print("\n[Compilation] Using default initial state |0...0⟩ (no X gates applied)")

        print(f"\n[Compilation] Starting workload processing: {len(workload)} instructions")

        # ──────────────────────────────────────────────────────────
        # Phase 1: Process workload instructions
        # ──────────────────────────────────────────────────────────

        for instruction in workload:
            print(f"  [Instruction] {instruction}")

            if instruction.startswith("IDLE_"):
                # IDLE instruction: Apply thermal relaxation via native 'id' gate
                # Each IDLE unit maps to one identity gate with attached thermal noise
                num_units = int(instruction.split("_")[1])
                time_ns = num_units * self.time_idle_ns
                
                print(f"    -> Wear-down sequence: {num_units} idle units ({time_ns:.0f} ns total)")
                
                # Apply native identity gate to operation register
                # The thermal_relaxation_error attached to 'id' will be applied
                for _ in range(num_units):
                    qc.id(qr_opreg)
                
                # Optional: Also apply to inactive memory registers for complete wear-down modeling
                for i in range(self.R):
                    qr_mem = self._built_registers[f"mem_{i}"]
                    for _ in range(num_units):
                        for qubit in qr_mem:
                            qc.id(qubit)
                
            elif instruction.startswith("READ_"):
                # READ instruction: READ_ij where ij is binary address
                address_binary = instruction.split("_")[1]
                logical_addr = int(address_binary, 2)  # Binary to decimal

                if logical_addr >= self.R:
                    raise ValueError(f"Logical address {logical_addr} out of range [0, {self.R - 1}]")

                print(f"    -> READ from Mem[{logical_addr}]")

                # Get source register
                source_reg = self._built_registers[f"mem_{logical_addr}"]

                # Apply SWAP between source and OpReg
                qc = self.work_phase.apply_swap(qc, source_reg, qr_opreg)



            elif instruction.startswith("WRITE_"):
                # WRITE instruction: WRITE_ij
                address_binary = instruction.split("_")[1]
                logical_addr = int(address_binary, 2)

                if logical_addr >= self.R:
                    raise ValueError(f"Logical address {logical_addr} out of range [0, {self.R - 1}]")

                print(f"    -> WRITE to Mem[{logical_addr}]")

                # Get destination register
                dest_reg = self._built_registers[f"mem_{logical_addr}"]

                # Apply SWAP between OpReg and destination
                qc = self.work_phase.apply_swap(qc, qr_opreg, dest_reg)



            else:
                print(f"  [WARNING] Unknown instruction: {instruction}")
            qc.barrier()  # Prevent inter-SWAP optimization
            #print(qc.draw(output="text"))   

        print(f"[Compilation] Workload processing complete")
        return qc

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

        # ──────────────────────────────────────────────────────────
        # SEED SETUP FOR REPRODUCIBILITY
        # ──────────────────────────────────────────────────────────
        random.seed(42)
        np.random.seed(42)

        print(f"\n[Simulation] Preparing circuit for {shots} shots")
        print(f"[Simulation] Seeds configured for reproducibility")

        try:
            qc_measured = circuit.copy()
            
            # ALWAYS add a specific register for final fidelity
            cr_final = ClassicalRegister(self.n, name="final_meas")
            qc_measured.add_register(cr_final)

            # Determine target register based on architecture
            logical_addr = 0
            if hasattr(self, 'location_map'): # SQTM Logic
                if self.location_map[logical_addr] == "O":  # type: ignore
                    target_reg = self._built_registers[f"mem_orig_{logical_addr}"]
                else:
                    target_reg = self._built_registers[f"mem_backup_{logical_addr}"]
            else: # SWAP only Logic
                target_reg = self._built_registers[f"mem_{logical_addr}"]

            # Measure ONLY the target register into cr_final
            for i in range(self.n):
                qc_measured.measure(target_reg[i], cr_final[i])

            print("[Transpile] Translating to hardware topology with seed=42...")
            
            # Extract initial layout before transpilation
            initial_layout = self._get_initial_layout(qc_measured)
            initial_layout = self._get_initial_layout(qc_measured)
            print(qc_measured.draw(output="text"))
            print("[Noise Model] Extracting noise characteristics...")
            
            # Initialize simulator with MPS method and fixed seed (matching SQTM)
            simulator = AerSimulator(
                noise_model=self.noise_model,
                method='matrix_product_state',
                seed_simulator=42
            )
            
            # Transpile with seed for reproducibility
            qc_transpiled = transpile(
                qc_measured,
                backend=self.backend,
                optimization_level=0,
                initial_layout=initial_layout,
                seed_transpiler=42
            )
            
            print(f"[Simulator] Running {shots} shots with fixed seed...")
            job = simulator.run(qc_transpiled, shots=shots, seed=42)
            result = job.result()
            
            counts = result.get_counts()
            total_counts = sum(counts.values())
            
            # Extract results: The last added classical register is always the first block (leftmost) in Qiskit output
            fidelity_count = 0
            target_state = ('1' * self.n) if self.initial_state == 1 else ('0' * self.n)
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
            
            state_label = "|1...1>" if self.initial_state == 1 else "|0...0>"
            print(f"  Fidelity ({state_label} success): {fidelity:.4f}")
            
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
            "logical_to_physical_map": self.logical_to_physical_map,
            "available_qubits": len(self.qubit_mapper.available_qubits),
        }


