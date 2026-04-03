import math
import os
import numpy as np
from scipy.optimize import curve_fit
import matplotlib
matplotlib.use("Agg")           # Non-interactive backend — output to file
import matplotlib.pyplot as plt

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel
from qiskit_ibm_runtime.fake_provider import FakeKyiv


# =============================================================================
# Magesan decay model (global reusable function)
# =============================================================================

def rb_decay_model(m: float, A: float, p: float, B: float) -> float:
    """
    Exponential decay model for Randomized Benchmarking (Magesan 2012).

    F(m) = A * p^m + B

    Parameters
    ----------
    m : float   Sequence length (number of cycles / SWAPs).
    A : float   Contrast factor; absorbs SPAM errors.
    p : float   Process decay parameter.
    B : float   Maximum mixing asymptote (ideal: 1/d for d-dimensional system).

    Returns
    -------
    float  — Predicted fidelity from the RB model.
    """
    return A * (p ** m) + B


# =============================================================================
# Main class
# =============================================================================

class CMaxValidator:
    """
    Scientific validator for the C_MAX parameter of the SQTM model.

    Implements the complete two-phase protocol:

    Phase 1 — RB Characterization (Magesan 2012)
        Measures F_emp(m) for multiple sequence lengths and fits F(m) = A*p^m + B
        to extract purified process error: r = ((d-1)/d)*(1-p).

    Phase 2 — C_MAX Calculation
        Analytically solves for operation threshold: m such that F(m) >= F_target.

    Usage Flow
    ----------
        validator = CMaxValidator(N=2)
        popt = validator.run_rb_characterization([0, 1, 2, 4, 6, 8, ...])
        r_emp = validator.print_rb_results(popt)
        c_max = validator.calculate_final_cmax(target_fidelity=0.90)
        validator.run_extrapolation_test(n=3)
    """
    
    # Candidate 2-qubit gates, in order of priority.
    # IBM Kyiv (Eagle r3) uses ECR natively; other platforms use CX.
    _TWO_QUBIT_GATE_CANDIDATES = ["ecr", "cx", "cz", "rzx"]

    # ── Constructor ──────────────────────────────────────────────────────────

    def __init__(self, N: int = 1) -> None:
        """
        Initialize the validator by extracting calibration parameters from
        FakeKyiv backend and constructing the noise model for simulation.

        Parameters
        ----------
        N : int  Word width of the SQTM register (qubits per register).
               Total circuit will have 2*N physical qubits. Default: 1.

        Public Attributes Initialized Here
        -----------------------------------
        N                : int — word width of the register
        d                : int — Hilbert space dimension (2^(2*N))
        B_ideal          : float — ideal noise floor (1/d)
        backend          : FakeKyiv  — calibration backend
        noise_model      : NoiseModel — full noise model (T1/T2 + depolarization)
        native_2q_gate   : str — detected native 2Q gate name
        cx_error         : float — average 2Q gate error
        p_swap_teorico   : float — theoretical SWAP error = 1-(1-p_2q)^(3*N)

        Attributes Available After Calling print_rb_results()
        -------------------------------------------------------
        A_fit, p_fit, B_fit : float — fitted Magesan parameters
        r_empirico          : float — process error without SPAM
        """
        # 0. Dynamic word width parameter
        self.N = N
        self.d = 2 ** (2 * N)
        self.B_ideal = 1.0 / self.d

        # 1. Reference backend (calibration snapshot from real IBM Kyiv)
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
        """
        Extract average error of the native 2-qubit gate from the backend.

        Searches in order ECR -> CX -> CZ -> RZX and averages over all
        qubit pairs, avoiding bias from atypical connections.

        Returns
        -------
        float  — Average error in (0, 1).

        Raises
        ------
        RuntimeError  — If no known 2Q gate is found.
        """
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

    # ── Extraction of disjoint qubit pairs ────────────────────────────────────

    def _get_physical_pairs(self) -> list[tuple[int, int]]:
        """
        Inspect hardware topology (coupling_map) and find self.N disjoint
        physical qubit pairs (no qubits shared between pairs).

        Returns
        -------
        list[tuple[int, int]]  — List of self.N disjoint (a, b) pairs.

        Raises
        ------
        ValueError  — If insufficient disjoint pairs are available.
        """
        coupling_map = self.backend.coupling_map
        edges = coupling_map.get_edges()

        # Convert to bidirectional tuple list
        # (ensure both directions are available)
        all_edges = set()
        for a, b in edges:
            all_edges.add((a, b))
            all_edges.add((b, a))

        # Find self.N disjoint pairs using greedy algorithm
        physical_pairs: list[tuple[int, int]] = []
        used_qubits: set[int] = set()

        for q1, q2 in edges:
            # If both qubits are available and pair exists
            if q1 not in used_qubits and q2 not in used_qubits:
                physical_pairs.append((q1, q2))
                used_qubits.add(q1)
                used_qubits.add(q2)
                if len(physical_pairs) == self.N:
                    return physical_pairs

        # If we reach here, insufficient disjoint pairs
        raise ValueError(
            f"Hardware does not support this word width. "
            f"Need {self.N} disjoint pairs but only found "
            f"{len(physical_pairs)}. Backend: {self.backend.name}."
        )

    # ── Empirical fidelity (noisy WorkPhase) ──────────────────────────────────

    def empirical_fidelity(self, n_swaps: int, shots: int = 4000) -> float:
        """
        Measure survival probability of base state |0...0> after n_swaps cycles
        of WorkPhase in the FakeKyiv noisy simulator.

        Circuit: n_swaps * [parallel SWAP of N pairs (i, i+N) | barrier]
               where each SWAP = [CNOT(i,i+N) -> CNOT(i+N,i) -> CNOT(i,i+N)]
        Barriers prevent the transpiler from cancelling consecutive SWAPs.
        optimization_level=0 preserves exact gate count.

        Parameters
        ----------
        n_swaps : int   Number of WorkPhase cycles (RB sequence length).
        shots   : int   Statistical shots. Default: 4000.

        Returns
        -------
        float  — P(|0...0>) after n_swaps noisy SWAPs on 2*N qubits.
        """
        if n_swaps < 0:
            raise ValueError(f"n_swaps must be >= 0, received: {n_swaps}")

        qc = QuantumCircuit(2 * self.N, 2 * self.N)

        for _ in range(n_swaps):
            for i in range(self.N):
                qc.cx(i, i + self.N)        # CNOT1
                qc.cx(i + self.N, i)        # CNOT2
                qc.cx(i, i + self.N)        # CNOT3
            qc.barrier()   # Prevents inter-SWAP optimization by transpiler

        qc.measure(range(2 * self.N), range(2 * self.N))

        # ── Hardware-Aware Qubit Mapping ──────────────────────────────────────
        # Get disjoint physical pairs from backend
        physical_pairs = self._get_physical_pairs()

        # Build initial_layout: logical qubit -> physical qubit
        # Logical qubits 0..N-1 are Storage Register
        # Logical qubits N..2N-1 are Operation Register
        # For each operation pair i, assign:
        #   logical qubit i        -> first qubit of physical pair i
        #   logical qubit N+i      -> second qubit of physical pair i
        initial_layout: list[int] = [0] * (2 * self.N)
        for i, (phys_q1, phys_q2) in enumerate(physical_pairs):
            initial_layout[i] = phys_q1              # Storage qubit i
            initial_layout[self.N + i] = phys_q2     # Operation qubit i

        # ── Transpile with qubit mapping ──────────────────────────────────────
        sim  = AerSimulator(noise_model=self.noise_model)
        qc_t = transpile(qc, backend=sim, optimization_level=0, initial_layout=initial_layout)
        job  = sim.run(qc_t, shots=shots)
        counts: dict[str, int] = job.result().get_counts()

        zero_state = "0" * (2 * self.N)
        return counts.get(zero_state, 0) / shots

    # ── RB Characterization (Magesan) ─────────────────────────────────────────

    def run_rb_characterization(
        self,
        m_list: list[int],
        shots: int = 4000,
        plot_path: str | None = "results/rb_decay_curve.png",
    ) -> np.ndarray:
        """
        Execute the Randomized Benchmarking protocol on WorkPhase
        and fit the Magesan model F(m) = A*p^m + B via curve_fit.

        Fitting Parameters
        -------------------
        p0     : [A=0.75, p=0.90, B=ideal]  — physical initial estimate
        bounds : A in [0,1], p in [0,1], B dynamically around ideal floor
                 B must be near ideal noise floor 1/d for system.

        Parameters
        ----------
        m_list    : list[int]   Sequence lengths to measure.
        shots     : int         Shots per point. Default: 4000.
        plot_path : str | None  Path to save plot. None = no plot.

        Returns
        -------
        popt : np.ndarray  Optimal parameters [A_fit, p_fit, B_fit].
        """
        print("=" * 65)
        print("  SQTM -- Phase B: RB Characterization (Magesan Model)")
        print("=" * 65)
        print(f"\n  Backend      : {self.backend.name}")
        print(f"  Native gate  : {self.native_2q_gate.upper()}")
        print(f"  p_swap_theory: {self.p_swap_teorico:.6f}  "
              f"({self.p_swap_teorico * 100:.4f} %)")
        print(f"\n  Measuring F_emp(m) for m = {m_list} ...")
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
        """
        Assign RB fitting parameters to instance attributes,
        calculate purified empirical process error, and print report.

        Purified Error Formula (Magesan 2012, Eq. 5):
            r_empirical = (d - 1) / d * (1 - p_fit)

        Parameters
        ----------
        popt : np.ndarray   Optimal parameters [A, p, B] from fit.

        Returns
        -------
        float  — r_empirical, process error without SPAM contamination.
        """
        self.A_fit, self.p_fit, self.B_fit = popt

        self.r_empirico = ((self.d - 1) * (1.0 - self.p_fit)) / self.d

        print("\n" + "=" * 65)
        print("  SQTM -- RB Fit Results (Magesan 2012)")
        print("=" * 65)

        print(f"\n  Model: F(m) = A * p^m + B")
        print(f"  {'Parameter':<12}  {'Value':>12}  Interpretation")
        print(f"  {'-'*52}")
        print(f"  {'A':<12}  {self.A_fit:>12.6f}  SPAM contrast (state prep + measurement)")
        print(f"  {'p':<12}  {self.p_fit:>12.6f}  Process decay per SWAP")
        print(f"  {'B':<12}  {self.B_fit:>12.6f}  Maximum mixing asymptote (ideal: 1/d={self.B_ideal:.4f})")

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
            print(f"    Parameters A and B capture SPAM effects that")
            print(f"    the pure i.i.d. model cannot represent.")
        else:
            print(f"    [EQUIVALENT] Difference = {diff_rel:.2f} % < 5 %.")
            print(f"    Errors are essentially equal; the i.i.d. model")
            print(f"    is sufficient for this operation range.")

        print("=" * 65)
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

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.scatter(m_arr, y_data, color="steelblue", zorder=5,
                   label="F_emp(m) — noisy simulation")
        ax.plot(m_dense, f_fit, color="crimson", linewidth=2,
                label=f"Magesan fit: A={A_fit:.3f}, p={p_fit:.4f}, B={B_fit:.3f}")
        ax.axhline(y=B_fit, linestyle="--", color="gray", alpha=0.6,
                   label=f"Asymptote B = {B_fit:.3f}")
        ax.set_xlabel("m  (number of SWAPs)", fontsize=12)
        ax.set_ylabel("F(m)  — base state survival", fontsize=12)
        ax.set_title("SQTM — RB Decay Curve (Magesan 2012) N={}".format(self.N), fontsize=13)
        ax.legend(fontsize=10)
        ax.grid(alpha=0.3)
        ax.set_ylim(0, 1.05)

        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)
        print(f"\n  [PLOT] RB curve saved to: {path}")

    # ── Predicted fidelity from Magesan model ─────────────────────────────────

    def theoretical_fidelity(self, n_swaps: int) -> float:
        """
        Fidelity predicted by the fitted Magesan model: F(m) = A*p^m + B.

        Requires calling print_rb_results() first so that
        self.A_fit, self.p_fit, and self.B_fit are assigned.

        Parameters
        ----------
        n_swaps : int  Number of SWAPs to evaluate.

        Returns
        -------
        float  — F(n_swaps) from the fitted RB model.
        """
        if n_swaps < 0:
            raise ValueError(f"n_swaps must be >= 0, received: {n_swaps}")
        return self.A_fit * self.p_fit ** n_swaps + self.B_fit

    # ── Extrapolation validation (n vs 2n) ─────────────────────────────────────

    def run_extrapolation_test(self, n: int = 10) -> None:
        """
        Compare F_theory(n) vs F_empirical(n) using the fitted Magesan model.

        Requires calling print_rb_results() first.

        Parameters
        ----------
        n : int  Base point for extrapolation. Default: 10.
        """
        gate_label = self.native_2q_gate.upper()
        print("=" * 65)
        print(f"  SQTM -- Phase B.4: Extrapolation Validation (n={n})")
        print("=" * 65)
        print(f"\n  p_{gate_label.lower()} = {self.cx_error:.6f}  |  "
              f"r_empirical = {self.r_empirico/(3*self.N):.6f}")

        f_th  = self.theoretical_fidelity(n)
        f_emp = self.empirical_fidelity(n)
        diff  = abs(f_th - f_emp)
        rel   = (diff / f_emp * 100) if f_emp > 0 else float("inf")
        print(f"\n  [n={n}]  F_model={f_th:.6f}  F_emp={f_emp:.6f}  "
              f"diff={diff:.6f} ({rel:.2f} %)")

        print("=" * 65)

    # ── Final C_MAX calculation (Magesan model) ───────────────────────────────

    def calculate_final_cmax(self, target_fidelity: float = 0.90) -> int:
        """
        Calculate C_MAX using the RB fitting parameters from Magesan.

        Requires calling print_rb_results() first.

        Analytical Derivation
        ---------------------
        Solving m from F(m) = A*p^m + B >= F_target:

            p^m >= (F_target - B) / A
            m   <= log((F_target - B) / A) / log(p)

        C_MAX = floor( log((F_target - B) / A) / log(p) )

        Parameters
        ----------
        target_fidelity : float  Fidelity threshold target. Default: 0.90.

        Returns
        -------
        int  — C_MAX: maximum SWAPs before falling below target_fidelity.

        Raises
        ------
        ValueError   — If target_fidelity is outside physical range (B, A+B].
        RuntimeError — If p_fit is outside interval (0, 1).
        """
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
    # 1. DEFINE THE ARCHITECTURE (N = Word width)
    N_qubits = 3
    validator = CMaxValidator(N=N_qubits)

    # ── Phase B.1: Complete RB characterization ───────────────────────────────
    m_list = [0, 1, 2, 4, 6, 8, 10, 15, 20, 25, 30, 40, 50]
    popt = validator.run_rb_characterization(m_list, shots=4000)

    # ── Phase B.2: Print results and validate model ───────────────────────────
    r_emp = validator.print_rb_results(popt)

    # ── Phase B.3: Calculate C_MAX with target fidelity ──────────────────────
    c_max = validator.calculate_final_cmax(target_fidelity=0.75)
    print(f"\n[FINAL RESULT]  C_MAX = {c_max} SWAPs  "
          f"(r_emp = {r_emp:.4f},  p_swap_theory = {validator.p_swap_teorico:.4f})")

    # ── Phase B.4: Extrapolation validation (Magesan model vs empirical) ──────
    # Change 'x' to compare the fitted model against a new measurement.
    x = 15
    validator.run_extrapolation_test(n=x)
    print(f"\n  Interpretation:")
    print(f"    If diff < 5%, the Magesan model extrapolates correctly to n={x}.")
    print(f"    r_emp={r_emp:.4f}  vs  p_swap_theory={validator.p_swap_teorico:.4f}")
