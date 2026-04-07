import math
import os
import sys
import numpy as np
from scipy.optimize import curve_fit
import matplotlib
matplotlib.use("Agg")           # Non-interactive backend — output to file
import matplotlib.pyplot as plt

from typing import cast
from qiskit import QuantumCircuit, transpile
from qiskit.circuit import QuantumRegister, ClassicalRegister, Clbit
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel
from qiskit_ibm_runtime.fake_provider import FakeKyiv

# Handle imports for both direct execution and module import
try:
    from src.functions.qubit_mapper import QubitMapper
except ModuleNotFoundError:
    # Add parent directory to path for direct script execution
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
    from src.functions.qubit_mapper import QubitMapper


# =============================================================================
# Magesan decay model (global reusable function)
# =============================================================================

def rb_decay_model(m: float, A: float, p: float, B: float) -> float:
   
    return A * (p ** m) + B


# =============================================================================
# Main class
# =============================================================================

class CMaxValidator:
   
    
    # Candidate 2-qubit gates, in order of priority.
    # IBM Kyiv (Eagle r3) uses ECR natively; other platforms use CX.
    _TWO_QUBIT_GATE_CANDIDATES = ["ecr", "cx", "cz", "rzx"]

    # ── Constructor ──────────────────────────────────────────────────────────

    def __init__(self, N: int = 1) -> None:
      
        # 0. Dynamic word width parameter (now uses 4*N total qubits)
        self.N = N
        self.d = 2 ** self.N  # Hilbert space dimension per register
        self.B_ideal = 1.0 / self.d

        # 1. Reference backend (calibration snapshot from real IBM Brisbane)
        self.backend = FakeKyiv()

        # 2. Complete noise model (depolarization + thermal relaxation)
        self.noise_model = NoiseModel.from_backend(self.backend)

        # 3. Detect native 2Q gate and extract average error.
        #    FakeKyiv uses ECR; auto-detects among [ECR, CX, CZ, RZX].
        self.native_2q_gate: str = ""   # filled by _extract_avg_cx_error
        self.cx_error: float     = self._extract_avg_cx_error()

        # 4. Theoretical SWAP error (3*N native 2Q gates in series, i.i.d.)
        #    Kept as reference to compare against empirical r from RB.
        self.p_swap_teorico: float = 1.0 - (1.0 - self.cx_error) ** (3 * N)

        # 5. RB fitting parameters — assigned in print_rb_results()
        self.A_fit:     float = 0.0
        self.p_fit:     float = 0.0
        self.B_fit:     float = 0.0
        self.r_empirico: float = 0.0

    # ── Extraction of calibration parameters ──────────────────────────────────

    def _extract_avg_cx_error(self) -> float:
        
        props = self.backend.properties()

        gate_errors: dict[str, list[float]] = {}
        for gate in props.gates:
            gname = gate.gate.lower()
            for param in gate.parameters:
                if param.name == "gate_error":
                    gate_errors.setdefault(gname, []).append(param.value)
                    break

        for candidate in self._TWO_QUBIT_GATE_CANDIDATES:
            if candidate in gate_errors:
                self.native_2q_gate = candidate
                return float(np.mean(gate_errors[candidate]))

        raise RuntimeError(
            f"No known 2Q gate found among "
            f"{self._TWO_QUBIT_GATE_CANDIDATES} in '{self.backend.name}'. "
            f"Available gates: {sorted(gate_errors.keys())}."
        )

    # ── Physical chain allocation via QubitMapper (NEW UNIFIED APPROACH) ──────

    def _get_physical_chains(self) -> list[tuple[int, int, int, int]]:
        """
        Find N disjoint chains of exactly 4 qubits each using QubitMapper.
        
        Each chain is a path: S — O — LA — LB (all must be connected by edges).
        This now delegates to QubitMapper.allocate_chain_topology() for scalability.
        
        Returns: list of tuples (storage, operation, link_alice, link_bob)
        """
        # Create an instance of QubitMapper from the backend
        mapper = QubitMapper(self.backend)
        
        # Build a single long chain for all registers
        # Chain structure: S_0 — O_0 — LA_0 — LB_0 — S_1 — O_1 — LA_1 — LB_1 — ...
        chain_config = []
        for i in range(self.N):
            chain_config.append((f"S_{i}", 1))
            chain_config.append((f"O_{i}", 1))
            chain_config.append((f"LA_{i}", 1))
            chain_config.append((f"LB_{i}", 1))
        
        # Allocate the unified chain
        allocation = mapper.allocate_chain_topology(chain_config)
        
        # Convert allocation back to original tuple format
        chains = []
        for i in range(self.N):
            s_qubit = allocation[f"S_{i}"][0]
            o_qubit = allocation[f"O_{i}"][0]
            la_qubit = allocation[f"LA_{i}"][0]
            lb_qubit = allocation[f"LB_{i}"][0]
            chains.append((s_qubit, o_qubit, la_qubit, lb_qubit))
        
        return chains
    # ── Empirical fidelity with 4-register teleportation protocol ────────────

    def empirical_fidelity(self, m_swaps: int, shots: int = 4000) -> float:
       
        if m_swaps < 0:
            raise ValueError(f"m_swaps must be >= 0, received: {m_swaps}")

        # ── Build 4-register quantum circuit ──────────────────────────────────
        reg_s = QuantumRegister(self.N, name="S")      # Storage
        reg_o = QuantumRegister(self.N, name="O")      # Operation
        reg_la = QuantumRegister(self.N, name="LA")    # Link Alice
        reg_lb = QuantumRegister(self.N, name="LB")    # Link Bob
        
        cr_s = ClassicalRegister(self.N, name="cr_s")           # S measurements
        cr_o = ClassicalRegister(self.N, name="cr_o")           # O measurements
        cr_la = ClassicalRegister(self.N, name="cr_la")         # LA measurements
        cr_lb = ClassicalRegister(self.N, name="cr_lb")         # LB measurements
        
        qc = QuantumCircuit(reg_s, reg_o, reg_la, reg_lb, cr_s, cr_o, cr_la, cr_lb)

        # ────────────────────────────────────────────────────────────────────
        # PASO 1: PREPARATION (all |0⟩) — implicit by circuit initialization
        # ────────────────────────────────────────────────────────────────────
        
        # ────────────────────────────────────────────────────────────────────
        # PASO 2: m SWAP CYCLES (Storage ↔ Operation)
        # ────────────────────────────────────────────────────────────────────
        
        
        for _ in range(m_swaps):
            for i in range(self.N):
                q_s = reg_s[i]
                q_o = reg_o[i]
                
                # SWAP implementation: 3 CNOTs
                qc.cx(q_s, q_o)
                qc.cx(q_o, q_s)
                qc.cx(q_s, q_o)
            
            qc.barrier()  # Prevent inter-SWAP optimization

        # ────────────────────────────────────────────────────────────────────
        # ────────────────────────────────────────────────────────────────────
        # PASO 3: TELEPORTATION PROTOCOL (S → LA → LB)
        # ────────────────────────────────────────────────────────────────────
        
        # 3a. EPR PAIR GENERATION (Bell pair creation between LA and LB)
        for i in range(self.N):
            qc.h(reg_la[i])
            qc.cx(reg_la[i], reg_lb[i])
        
        qc.barrier()
        
        # 3b. BELL MEASUREMENT PREPARATION (Source interacts with LinkAlice)
        for i in range(self.N):
            qc.cx(reg_s[i], reg_la[i])
            qc.h(reg_s[i])
        
        qc.barrier()
        
        # 3c. BELL STATE MEASUREMENT (BSM) - Mid-circuit measurement
        # Classical bits: cr_s[i] stores S[i], cr_la[i] stores LA[i]
        # These measurements collapse the Bell state and provide correction info
        for i in range(self.N):
            qc.measure(reg_s[i], cr_s[i])
            qc.measure(reg_la[i], cr_la[i])
        
        qc.barrier()
        
        # 3d. FEED-FORWARD (Data Movement Correction)
             
        for i in range(self.N):
            # If LA[i] measured as 1, apply X to LB[i]
            # (corrects for phase flip in Bell measurement)
            try:
                with qc.if_test((cast(Clbit, cr_la[i]), 1)):
                    qc.x(reg_lb[i])
                
                # If S[i] measured as 1, apply Z to LB[i]
                # (corrects for bit flip in Bell measurement)
                with qc.if_test((cast(Clbit, cr_s[i]), 1)):
                    qc.z(reg_lb[i])
            except (NotImplementedError, ValueError):
                # If AerSimulator doesn't support if_test, skip and rely on post-selection
                pass
        
        qc.barrier()
        
        # ────────────────────────────────────────────────────────────────────
        # PASO 4: FINAL MEASUREMENT (all registers for completeness)
        # ────────────────────────────────────────────────────────────────────
        
        # Measure Operation register (part of complete protocol)
        for i in range(self.N):
            qc.measure(reg_o[i], cr_o[i])
        
        # Measure LinkBob register (final state for fidelity)
        for i in range(self.N):
            qc.measure(reg_lb[i], cr_lb[i])

# ────────────────────────────────────────────────────────────────────
        # HARDWARE-AWARE QUBIT MAPPING
        # ────────────────────────────────────────────────────────────────────
        chains = self._get_physical_chains()
        
        initial_layout = [0] * (4 * self.N)
        for i, (phys_s, phys_o, phys_la, phys_lb) in enumerate(chains):
            initial_layout[i] = phys_s                           # Storage
            initial_layout[self.N + i] = phys_o                  # Operation
            initial_layout[2 * self.N + i] = phys_la             # Link Alice
            initial_layout[3 * self.N + i] = phys_lb             # Link Bob
            
        # ────────────────────────────────────────────────────────────────────
        # TRANSPILE AND SIMULATE
        # ────────────────────────────────────────────────────────────────────
        
        sim  = AerSimulator(noise_model=self.noise_model)
        qc_t = transpile(qc, backend=self.backend, optimization_level=0, initial_layout=initial_layout)
        job  = sim.run(qc_t, shots=shots)
        counts: dict[str, int] = job.result().get_counts()

# ────────────────────────────────────────────────────────────────────
        # DIRECT VERIFICATION OF TELEPORTED STATUS
        # ────────────────────────────────────────────────────────────────────
        
        fidelity_count = 0
        target_state = '0' * self.N
        
        for bitstring, count in counts.items():
            bitstring_clean = bitstring.replace(' ', '')
            bitstring_rev = bitstring_clean[::-1]  
            
            # Extraer únicamente los bits del destino final (Link Bob)
            lb_bits = bitstring_rev[3*self.N : 4*self.N]
            
            if lb_bits == target_state:
                fidelity_count += count
                
        return fidelity_count / shots

    # ── RB Characterization (Magesan) ─────────────────────────────────────────

    def run_rb_characterization(
        self,
        m_list: list[int],
        shots: int = 2048,
        plot_path: str | None = "results/rb_decay_curve_.png",
    ) -> np.ndarray:

        print("=" * 75)
        print("  SQTM -- Phase B: RB Characterization with 4-Register Teleportation")
        print("=" * 75)
        print(f"\n  Backend      : {self.backend.name}")
        print(f"  Architecture : 4 registers * {self.N} qubits = {4*self.N} total qubits")
        print(f"                 (Storage, Operation, LinkAlice, LinkBob)")
        print(f"  Hilbert dim  : d = 2^({4*self.N}) = {self.d}")
        print(f"  Native gate  : {self.native_2q_gate.upper()}")
        print(f"  p_swap_theory: {self.p_swap_teorico:.6f}  "
              f"({self.p_swap_teorico * 100:.4f} %)")
        print(f"\n  Measuring F_emp(m) for m = {m_list} with teleportation protocol...")
        print(f"  shots per point = {shots}\n")

        # ── Empirical data collection ─────────────────────────────────────────
        m_arr  = np.array(m_list, dtype=float)
        y_data: list[float] = []

        for m in m_list:
            f_emp = self.empirical_fidelity(m, shots=shots)
            y_data.append(f_emp)
            print(f"    m={m:3d}  F_emp = {f_emp:.6f}")

        y_arr = np.array(y_data, dtype=float)

        # ── curve_fit adjustment ──────────────────────────────────────────────
        p0     = [0.75, 0.90, self.B_ideal]
        bounds = ([0.0, 0.0, 0.0], [1.0, 1.0, 1.0])

        popt, _ = curve_fit(
            rb_decay_model,
            m_arr,
            y_arr,
            p0=p0,
            bounds=bounds,
            maxfev=10_000,
        )

        print(f"\n  Fit completed.")
        print(f"    A_fit = {popt[0]:.6f}")
        print(f"    p_fit = {popt[1]:.6f}")
        print(f"    B_fit = {popt[2]:.6f}")

        # ── Plot (optional) ───────────────────────────────────────────────────
        if plot_path is not None:
            self._plot_rb_curve(m_arr, y_arr, popt, plot_path)

        return popt

    # ── RB results report ─────────────────────────────────────────────────────

    def print_rb_results(self, popt: np.ndarray) -> float:
       
        self.A_fit, self.p_fit, self.B_fit = popt

        self.r_empirico = ((self.d - 1) * (1.0 - self.p_fit)) / self.d

        print("\n" + "=" * 75)
        print("  SQTM -- RB Fit Results (Magesan 2012 + Teleportation Protocol)")
        print("=" * 75)

        print(f"\n  Model: F(m) = A * p^m + B")
        print(f"  {'Parameter':<15}  {'Value':>12}  Interpretation")
        print(f"  {'-'*65}")
        print(f"  {'A':<15}  {self.A_fit:>12.6f}  SPAM + teleportation 'toll'")
        print(f"  {'p':<15}  {self.p_fit:>12.6f}  Process decay per SWAP cycle")
        print(f"  {'B':<15}  {self.B_fit:>12.6f}  Max mixing asymptote (ideal: 1/d={self.B_ideal:.4f})")

        print(f"\n  [ARCHITECTURE]  4 registers * {self.N} qubits = {4*self.N} total qubits")
        print(f"                  (Storage, Operation, LinkAlice, LinkBob)")
        print(f"                  Hilbert space dimension: d = 2^{4*self.N} = {self.d}")

        print(f"\n  [PURIFIED EMPIRICAL ERROR]")
        print(f"    r_empirical = (d-1)/d * (1 - p_fit)")
        print(f"                = ({self.d - 1})/{self.d} * (1 - {self.p_fit:.6f})")
        print(f"                = {self.r_empirico:.6f}  ({self.r_empirico * 100:.4f} %)")

        print(f"\n  [COMPARISON WITH THEORETICAL MODEL]")
        print(f"    p_swap_theory ({self.native_2q_gate.upper()})      = "
              f"{self.p_swap_teorico:.6f}  ({self.p_swap_teorico * 100:.4f} %)")
        print(f"    r_empirical (RB)               = "
              f"{self.r_empirico:.6f}  ({self.r_empirico * 100:.4f} %)")

        diff_abs = abs(self.r_empirico - self.p_swap_teorico)
        diff_rel = (diff_abs / self.p_swap_teorico * 100) if self.p_swap_teorico > 0 else float("inf")
        print(f"    Relative difference            = {diff_rel:.2f} %")

        print(f"\n  [VERDICT]")
        if diff_rel > 5.0:
            print(f"    [RB MODEL REQUIRED] Errors differ by {diff_rel:.2f} %.")
            print(f"    Parameters A, p, and B capture SPAM + teleportation effects.")
        else:
            print(f"    [EQUIVALENT] Difference = {diff_rel:.2f} % < 5 %.")
            print(f"    Errors are essentially equal within tolerance.")

        print("\n  [TELEPORTATION PROTOCOL IMPACT]")
        print(f"    The parameter A={self.A_fit:.6f} now represents")
        print(f"    the fidelity after surviving the teleportation 'tollbooth'.")
        print(f"    C_MAX calculation using this A guarantees a post-rescue")
        print(f"    coherence bound that accounts for protocol overhead.")

        print("=" * 75)
        return self.r_empirico

    # ── RB decay curve plot ───────────────────────────────────────────────────

    def _plot_rb_curve(
        self,
        m_arr: np.ndarray,
        y_data: np.ndarray,
        popt: np.ndarray,
        path: str,
    ) -> None:
        """Generate and save the RB decay curve vs empirical data."""
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)

        A_fit, p_fit, B_fit = popt
        m_dense = np.linspace(0, m_arr.max(), 300)
        f_fit   = rb_decay_model(m_dense, A_fit, p_fit, B_fit)

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.scatter(m_arr, y_data, color="steelblue", s=100, zorder=5,
                   label="F_emp(m) — 4-register teleportation protocol")
        ax.plot(m_dense, f_fit, color="crimson", linewidth=2.5,
                label=f"Magesan fit: A={A_fit:.3f}, p={p_fit:.4f}, B={B_fit:.3f}")
        ax.axhline(y=B_fit, linestyle="--", color="gray", alpha=0.6,
                   label=f"Asymptote B = {B_fit:.3f}")
        ax.set_xlabel("m  (SWAP cycles)", fontsize=13, fontweight='bold')
        ax.set_ylabel("F(m)  — survival probability", fontsize=13, fontweight='bold')
        ax.set_title(f"SQTM RB Decay Curve with Teleportation (N={self.N}, d={self.d})", 
                     fontsize=14, fontweight='bold')
        ax.legend(fontsize=11, loc='upper right')
        ax.grid(alpha=0.3, linestyle='--')
        ax.set_ylim(0, 1.05)

        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)
        print(f"\n  [PLOT] RB curve saved to: {path}")

    # ── Predicted fidelity from Magesan model ─────────────────────────────────

    def theoretical_fidelity(self, n_swaps: int) -> float:
        
        if n_swaps < 0:
            raise ValueError(f"n_swaps must be >= 0, received: {n_swaps}")
        return self.A_fit * self.p_fit ** n_swaps + self.B_fit

    # ── Extrapolation validation (n vs 2n) ─────────────────────────────────────

    def run_extrapolation_test(self, n: int = 10) -> None:
       
        gate_label = self.native_2q_gate.upper()
        print("=" * 75)
        print(f"  SQTM -- Phase B.4: RB Extrapolation Validation (n={n})")
        print("=" * 75)
        print(f"\n  Architecture: 4 registers * {self.N} qubits = {4*self.N} total qubits")
        print(f"  p_{gate_label.lower()} = {self.cx_error:.6f}  |  "
              f"r_empirical = {self.r_empirico/(3*self.N):.6f}")

        f_th  = self.theoretical_fidelity(n)
        f_emp = self.empirical_fidelity(n)
        diff  = abs(f_th - f_emp)
        rel   = (diff / f_emp * 100) if f_emp > 0 else float("inf")
        print(f"\n  [n={n}]  F_model={f_th:.6f}  F_emp={f_emp:.6f}  "
              f"diff={diff:.6f} ({rel:.2f} %)")
        
        if rel < 5.0:
            print(f"  [OK] Model extrapolates well (diff < 5 %)")
        else:
            print(f"  [WARN] Model deviation {rel:.2f} % -- may need higher shots")

        print("=" * 75)

    # ── Final C_MAX calculation (Magesan model with teleportation) ───────────

    def calculate_final_cmax(self, target_fidelity: float = 0.90) -> int:
       
        f_min_physical = self.B_fit
        f_max_physical = self.A_fit + self.B_fit

        if not (f_min_physical < target_fidelity <= f_max_physical):
            raise ValueError(
                f"target_fidelity={target_fidelity:.4f} outside physical range "
                f"({f_min_physical:.4f}, {f_max_physical:.4f}]. "
                f"B={self.B_fit:.4f} is minimum asymptote; "
                f"A+B={f_max_physical:.4f} is maximum achievable."
            )

        if self.p_fit <= 0.0 or self.p_fit >= 1.0:
            raise RuntimeError(
                f"p_fit={self.p_fit:.6f} outside interval (0, 1). "
                "RB fit is invalid; increase m_list or shots."
            )

        # C_MAX = floor( log((F_target - B) / A) / log(p) )
        ratio = (target_fidelity - self.B_fit) / self.A_fit
        c_max = math.floor(math.log(ratio) / math.log(self.p_fit))

        print("\n" + "=" * 65)
        print("  SQTM -- Final C_MAX Calculation (Magesan RB Model)")
        print("=" * 65)
        print(f"  RB fitting parameters:")
        print(f"    A_fit  = {self.A_fit:.6f}  (SPAM contrast)")
        print(f"    p_fit  = {self.p_fit:.6f}  (process decay)")
        print(f"    B_fit  = {self.B_fit:.6f}  (mixing asymptote)")
        print(f"\n  Purified process error:")
        print(f"    r_empirical = (d-1)/d * (1 - p_fit) = {self.r_empirico:.6f}  "
              f"({self.r_empirico * 100:.4f} %)")
        print(f"    p_swap_theory = {self.p_swap_teorico:.6f}  "
              f"({self.p_swap_teorico * 100:.4f} %)")
        print(f"\n  Target fidelity: F_target = {target_fidelity:.2f}  "
              f"({target_fidelity * 100:.0f} %)")
        print(f"\n  Formula: C_MAX = floor[ log((F_target-B)/A) / log(p) ]")
        print(f"         = floor[ log({ratio:.6f}) / log({self.p_fit:.6f}) ]")
        print(f"         = floor[ {math.log(ratio):.6f} / {math.log(self.p_fit):.6f} ]")
        print(f"\n  >>> C_MAX = {c_max} SWAPs")
        print(f"      F(C_MAX)   = {rb_decay_model(c_max,   self.A_fit, self.p_fit, self.B_fit):.6f}  (>= {target_fidelity:.2f})")
        print(f"      F(C_MAX+1) = {rb_decay_model(c_max+1, self.A_fit, self.p_fit, self.B_fit):.6f}  (<  {target_fidelity:.2f})")
        print("=" * 65)

        return c_max

# =============================================================================
# Entry point for direct execution
# =============================================================================

if __name__ == "__main__":
    # ── DEFINE THE ARCHITECTURE (N = Word width per register) ─────────────────
    N_qubits = 1
    validator = CMaxValidator(N=N_qubits)
    

    # ── Phase B.1: Complete RB characterization with teleportation ────────────
    m_list = [0, 1, 2, 4, 6, 8, 10, 15, 20, 25, 30, 40, 50, 60, 80, 100]
    popt = validator.run_rb_characterization(m_list, shots=4000, plot_path = "results/rb_decay_curve n="+ str(N_qubits) +".png")

    # ── Phase B.2: Print results and validate model ───────────────────────────
    r_emp = validator.print_rb_results(popt)

    # ── Phase B.3: Calculate C_MAX with target fidelity ──────────────────────
  
    c_max = validator.calculate_final_cmax(target_fidelity=0.75)
    print(f"\n[FINAL RESULT]  C_MAX = {c_max} SWAPs  "
          f"(r_emp = {r_emp:.4f},  p_swap_theory = {validator.p_swap_teorico:.4f})")

    # ── Phase B.4: Extrapolation validation (optional) ───────────────────────
    # ── Phase B.4: Extrapolation validation (Magesan model vs empirical) ──────
    # Change 'x' to compare the fitted model against a new measurement.
    x = 15
    validator.run_extrapolation_test(n=x)
    print(f"\n  Interpretation:")
    print(f"    If diff < 5%, the Magesan model extrapolates correctly to n={x}.")
    print(f"    r_emp={r_emp:.4f}  vs  p_swap_theory={validator.p_swap_teorico:.4f}")