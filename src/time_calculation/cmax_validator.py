
import math
import os
import numpy as np
from scipy.optimize import curve_fit
import matplotlib
matplotlib.use("Agg")           # backend no interactivo — salida a archivo
import matplotlib.pyplot as plt

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel
from qiskit_ibm_runtime.fake_provider import FakeKyiv


# =============================================================================
# Modelo de decaimiento de Magesan (funcion global reutilizable)
# =============================================================================

def rb_decay_model(m: float, A: float, p: float, B: float) -> float:
    """
    Modelo de decaimiento exponencial de Magesan para Randomized Benchmarking.

    F(m) = A * p^m + B

    Parameters
    ----------
    m : float   Longitud de la secuencia (numero de ciclos / SWAPs).
    A : float   Factor de contraste; absorbe errores SPAM.
    p : float   Parametro de decaimiento del proceso.
    B : float   Asintota de mezcla maxima (ideal 1/d^2 = 0.25 para 2 qubits).

    Returns
    -------
    float  — Fidelidad de supervivencia predicha por el modelo RB.
    """
    return A * (p ** m) + B


# =============================================================================
# Clase principal
# =============================================================================

class CMaxValidator:
    """
    Validador cientifico para el parametro C_MAX del modelo SQTM.

    Implementa el protocolo completo en dos fases:

    Fase 1 — Caracterizacion RB (Magesan 2012)
        Mide F_emp(m) para multiples longitudes m y ajusta F(m) = A*p^m + B
        para extraer el error empirico purificado de SPAM: r = 0.75*(1-p).

    Fase 2 — Calculo de C_MAX
        Despeja analiticamente el umbral de operaciones: m tal que F(m) >= F_target.

    Flujo de uso
    ------------
        validator = CMaxValidator()
        popt = validator.run_rb_characterization([0, 1, 2, 4, 6, 8, 10, 15, 20, 25, 30])
        r_emp = validator.print_rb_results(popt)
        c_max = validator.calculate_final_cmax(target_fidelity=0.90)
        validator.run_extrapolation_test(n=3)
    """

    # Puertas de 2 qubits candidatas, en orden de prioridad.
    # IBM Kyiv (Eagle r3) usa ECR nativamente; otras plataformas usan CX.
    _TWO_QUBIT_GATE_CANDIDATES = ["ecr", "cx", "cz", "rzx"]

    # Dimension del espacio de Hilbert para 2 qubits: d = 2^2 = 4
    _HILBERT_DIM = 4

    # ── Constructor ──────────────────────────────────────────────────────────

    def __init__(self) -> None:
        """
        Inicializa el validador extrayendo los parametros de calibracion del
        backend FakeKyiv y construyendo el modelo de ruido para simulacion.

        Atributos publicos inicializados aqui
        --------------------------------------
        backend          : FakeKyiv  — backend de calibracion
        noise_model      : NoiseModel — modelo de ruido completo (T1/T2 + dep.)
        native_2q_gate   : str — nombre de la puerta nativa de 2Q detectada
        cx_error         : float — error promedio de la puerta nativa 2Q
        p_swap_teorico   : float — error SWAP teorico = 1-(1-p_2q)^3

        Atributos disponibles TRAS llamar a print_rb_results()
        --------------------------------------------------------
        A_fit, p_fit, B_fit : float — parametros ajustados del modelo Magesan
        r_empirico          : float — error de proceso sin SPAM
        """
        # 1. Backend de referencia (snapshot de calibracion real de IBM Kyiv)
        self.backend = FakeKyiv()

        # 2. Modelo de ruido completo (depolarizacion + relajacion termica)
        self.noise_model = NoiseModel.from_backend(self.backend)

        # 3. Detectar la puerta nativa de 2Q y extraer su error promedio.
        #    FakeKyiv usa ECR; auto-detecta entre [ECR, CX, CZ, RZX].
        self.native_2q_gate: str = ""   # se llena en _extract_avg_cx_error
        self.cx_error: float     = self._extract_avg_cx_error()

        # 4. Error SWAP teorico (3 puertas de 2Q nativas en serie, i.i.d.)
        #    Se conserva como referencia para comparar con r_empirico del RB.
        self.p_swap_teorico: float = 1.0 - (1.0 - self.cx_error) ** 3

        # 5. Parametros del ajuste RB — se asignan en print_rb_results()
        self.A_fit:     float = 0.0
        self.p_fit:     float = 0.0
        self.B_fit:     float = 0.0
        self.r_empirico: float = 0.0

    # ── Extraccion de parametros de calibracion ──────────────────────────────

    def _extract_avg_cx_error(self) -> float:
        """
        Extrae el error promedio de la puerta nativa de 2 qubits del backend.

        Busca en orden ECR -> CX -> CZ -> RZX y promedia sobre todos los
        pares de qubits, evitando sesgo por conexiones atipicas.

        Returns
        -------
        float  — Error promedio en (0, 1).

        Raises
        ------
        RuntimeError  — Si no se encuentra ninguna puerta de 2Q conocida.
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
            f"No se encontro ninguna puerta de 2Q conocida "
            f"{self._TWO_QUBIT_GATE_CANDIDATES} en '{self.backend.name}'. "
            f"Puertas disponibles: {sorted(gate_errors.keys())}."
        )

    # ── Fidelidad empirica (WorkPhase ruidosa) ───────────────────────────────

    def empirical_fidelity(self, n_swaps: int, shots: int = 4000) -> float:
        """
        Mide la probabilidad de supervivencia |00> tras n_swaps ciclos de
        WorkPhase en el simulador ruidoso de FakeKyiv.

        Circuito: n_swaps * [CX(0,1) -> CX(1,0) -> CX(0,1) | barrier]
        La barrera impide que el transpilador cancele SWAPs consecutivos.
        optimization_level=0 preserva el conteo de compuertas exacto.

        Parameters
        ----------
        n_swaps : int   Numero de ciclos WorkPhase (longitud de secuencia RB).
        shots   : int   Disparos estadisticos. Default: 4000.

        Returns
        -------
        float  — P(|00>) despues de n_swaps SWAPs ruidosos.
        """
        if n_swaps < 0:
            raise ValueError(f"n_swaps debe ser >= 0, recibido: {n_swaps}")

        qc = QuantumCircuit(2, 2)

        for _ in range(n_swaps):
            qc.cx(0, 1)    # CNOT1
            qc.cx(1, 0)    # CNOT2
            qc.cx(0, 1)    # CNOT3
            qc.barrier()   # Evita optimizacion inter-SWAP por el transpilador

        qc.measure([0, 1], [0, 1])

        sim  = AerSimulator(noise_model=self.noise_model)
        qc_t = transpile(qc, backend=sim, optimization_level=0)
        job  = sim.run(qc_t, shots=shots)
        counts: dict[str, int] = job.result().get_counts()

        return counts.get("00", 0) / shots

    # ── Caracterizacion RB (Magesan) ─────────────────────────────────────────

    def run_rb_characterization(
        self,
        m_list: list[int],
        shots: int = 4000,
        plot_path: str | None = "results/rb_decay_curve.png",
    ) -> np.ndarray:
        """
        Ejecuta el protocolo de Randomized Benchmarking sobre la WorkPhase
        y ajusta el modelo de Magesan F(m) = A*p^m + B via curve_fit.

        Parametros del ajuste
        ---------------------
        p0     : [A=0.75, p=0.90, B=0.25]  — estimacion inicial fisica
        bounds : A in [0,1], p in [0,1], B in [0.20, 0.30]
                 B debe rondar 1/d^2 = 0.25 para 2 qubits (d=4).

        Parameters
        ----------
        m_list    : list[int]   Longitudes de secuencia a medir.
        shots     : int         Disparos por punto. Default: 4000.
        plot_path : str | None  Ruta para guardar la grafica. None = sin grafica.

        Returns
        -------
        popt : np.ndarray  Parametros optimos [A_fit, p_fit, B_fit].
        """
        print("=" * 65)
        print("  SQTM -- Fase B: Caracterizacion RB (Modelo de Magesan)")
        print("=" * 65)
        print(f"\n  Backend      : {self.backend.name}")
        print(f"  Puerta nativa: {self.native_2q_gate.upper()}")
        print(f"  p_swap_teo   : {self.p_swap_teorico:.6f}  "
              f"({self.p_swap_teorico * 100:.4f} %)")
        print(f"\n  Midiendo F_emp(m) para m = {m_list} ...")
        print(f"  shots por punto = {shots}\n")

        # ── Recoleccion de datos empiricos ────────────────────────────────────
        m_arr  = np.array(m_list, dtype=float)
        y_data: list[float] = []

        for m in m_list:
            f_emp = self.empirical_fidelity(m, shots=shots)
            y_data.append(f_emp)
            print(f"    m={m:3d}  F_emp = {f_emp:.6f}")

        y_arr = np.array(y_data, dtype=float)

        # ── Ajuste curve_fit ──────────────────────────────────────────────────
        p0     = [0.75, 0.90, 0.25]
        bounds = ([0.0, 0.0, 0.20], [1.0, 1.0, 0.30])

        popt, _ = curve_fit(
            rb_decay_model,
            m_arr,
            y_arr,
            p0=p0,
            bounds=bounds,
            maxfev=10_000,
        )

        print(f"\n  Ajuste completado.")
        print(f"    A_fit = {popt[0]:.6f}")
        print(f"    p_fit = {popt[1]:.6f}")
        print(f"    B_fit = {popt[2]:.6f}")

        # ── Grafica (opcional) ────────────────────────────────────────────────
        if plot_path is not None:
            self._plot_rb_curve(m_arr, y_arr, popt, plot_path)

        return popt

    # ── Reporte de resultados RB ──────────────────────────────────────────────

    def print_rb_results(self, popt: np.ndarray) -> float:
        """
        Asigna los parametros del ajuste RB a los atributos de instancia,
        calcula el error empirico purificado de SPAM e imprime el reporte.

        Formula del error empirico (Magesan 2012, Eq. 5):
            r_empirico = (d - 1) / d * (1 - p_fit)
                       = 0.75 * (1 - p_fit)     para d=4 (2 qubits)

        Parameters
        ----------
        popt : np.ndarray   Parametros optimos [A, p, B] del ajuste.

        Returns
        -------
        float  — r_empirico, el error de proceso por SWAP sin contaminacion SPAM.
        """
        self.A_fit, self.p_fit, self.B_fit = popt

        d = self._HILBERT_DIM
        self.r_empirico = ((d - 1) * (1.0 - self.p_fit)) / d

        print("\n" + "=" * 65)
        print("  SQTM -- Resultados del Ajuste RB (Magesan 2012)")
        print("=" * 65)

        print(f"\n  Modelo: F(m) = A * p^m + B")
        print(f"  {'Parametro':<12}  {'Valor':>12}  Interpretacion")
        print(f"  {'-'*52}")
        print(f"  {'A':<12}  {self.A_fit:>12.6f}  Contraste SPAM (preparacion + medicion)")
        print(f"  {'p':<12}  {self.p_fit:>12.6f}  Decaimiento de proceso por SWAP")
        print(f"  {'B':<12}  {self.B_fit:>12.6f}  Asintota mezcla maxima (ideal: 1/d^2={1/d**2:.4f})")

        print(f"\n  [ERROR EMPIRICO PURIFICADO]")
        print(f"    r_empirico = (d-1)/d * (1 - p_fit)")
        print(f"               = 0.75 * (1 - {self.p_fit:.6f})")
        print(f"               = {self.r_empirico:.6f}  ({self.r_empirico * 100:.4f} %)")

        print(f"\n  [COMPARACION CON MODELO TEORICO]")
        print(f"    p_swap_teorico (3 x {self.native_2q_gate.upper()}) = "
              f"{self.p_swap_teorico:.6f}  ({self.p_swap_teorico * 100:.4f} %)")
        print(f"    r_empirico (RB)                   = "
              f"{self.r_empirico:.6f}  ({self.r_empirico * 100:.4f} %)")

        diff_abs = abs(self.r_empirico - self.p_swap_teorico)
        diff_rel = (diff_abs / self.p_swap_teorico * 100) if self.p_swap_teorico > 0 else float("inf")
        print(f"    Diferencia relativa               = {diff_rel:.2f} %")

        print(f"\n  [VEREDICTO]")
        if diff_rel > 5.0:
            print(f"    [MODELO RB NECESARIO] Los errores difieren un {diff_rel:.2f} %.")
            print(f"    Los parametros A y B capturan efectos SPAM que el")
            print(f"    modelo i.i.d. puro no puede representar.")
        else:
            print(f"    [EQUIVALENTES] Diferencia = {diff_rel:.2f} % < 5 %.")
            print(f"    Los errores son esencialmente iguales; el modelo")
            print(f"    i.i.d. es suficiente para este rango de operaciones.")

        print("=" * 65)
        return self.r_empirico

    # ── Grafica de la curva RB ────────────────────────────────────────────────

    def _plot_rb_curve(
        self,
        m_arr: np.ndarray,
        y_data: np.ndarray,
        popt: np.ndarray,
        path: str,
    ) -> None:
        """Genera y guarda la curva de decaimiento RB vs los datos empiricos."""
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)

        A_fit, p_fit, B_fit = popt
        m_dense = np.linspace(0, m_arr.max(), 300)
        f_fit   = rb_decay_model(m_dense, A_fit, p_fit, B_fit)

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.scatter(m_arr, y_data, color="steelblue", zorder=5,
                   label="F_emp(m) — simulacion ruidosa")
        ax.plot(m_dense, f_fit, color="crimson", linewidth=2,
                label=f"Ajuste Magesan: A={A_fit:.3f}, p={p_fit:.4f}, B={B_fit:.3f}")
        ax.axhline(y=B_fit, linestyle="--", color="gray", alpha=0.6,
                   label=f"Asintota B = {B_fit:.3f}")
        ax.set_xlabel("m  (numero de SWAPs)", fontsize=12)
        ax.set_ylabel("F(m)  — supervivencia |00>", fontsize=12)
        ax.set_title("SQTM — Curva de Decaimiento RB (Magesan 2012)", fontsize=13)
        ax.legend(fontsize=10)
        ax.grid(alpha=0.3)
        ax.set_ylim(0, 1.05)

        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)
        print(f"\n  [GRAFICA] Curva RB guardada en: {path}")

    # ── Fidelidad predicha por el modelo Magesan ─────────────────────────────

    def theoretical_fidelity(self, n_swaps: int) -> float:
        """
        Fidelidad predicha por el modelo Magesan ajustado: F(m) = A*p^m + B.

        Requiere haber llamado a print_rb_results() previamente para que
        self.A_fit, self.p_fit y self.B_fit esten asignados.

        Parameters
        ----------
        n_swaps : int  Numero de SWAPs a evaluar.

        Returns
        -------
        float  — F(n_swaps) segun el modelo RB ajustado.
        """
        if n_swaps < 0:
            raise ValueError(f"n_swaps debe ser >= 0, recibido: {n_swaps}")
        return self.A_fit * self.p_fit ** n_swaps + self.B_fit

    # ── Validacion de extrapolacion (n vs 2n) ────────────────────────────────

    def run_extrapolation_test(self, n: int = 10) -> None:
        """
        Compara F_teorica(n) vs F_empirica(n) usando el modelo Magesan ajustado.

        Requiere haber llamado a print_rb_results() previamente.

        Parameters
        ----------
        n : int  Punto base de extrapolacion. Default: 10.
        """
        gate_label = self.native_2q_gate.upper()
        print("=" * 65)
        print(f"  SQTM -- Fase B.4: Validacion de Extrapolacion (n=x={n})")
        print("=" * 65)
        print(f"\n  p_{gate_label.lower()} = {self.cx_error:.6f}  |  "
              f"r_empirico = {self.r_empirico/3:.6f}")

        f_th  = self.theoretical_fidelity(n)
        f_emp = self.empirical_fidelity(n)
        diff  = abs(f_th - f_emp)
        rel   = (diff / f_emp * 100) if f_emp > 0 else float("inf")
        print(f"\n  [n={n}]  F_modelo={f_th:.6f}  F_emp={f_emp:.6f}  "
              f"diff={diff:.6f} ({rel:.2f} %)")

        print("=" * 65)

    # ── Calculo final de C_MAX (modelo Magesan) ───────────────────────────────

    def calculate_final_cmax(self, target_fidelity: float = 0.90) -> int:
        """
        Calcula C_MAX usando los parametros del ajuste RB de Magesan.

        Requiere haber llamado a print_rb_results() previamente.

        Derivacion analitica
        --------------------
        Despejando m de F(m) = A*p^m + B >= F_target:

            p^m >= (F_target - B) / A
            m   <= log((F_target - B) / A) / log(p)

        C_MAX = floor( log((F_target - B) / A) / log(p) )

        Parameters
        ----------
        target_fidelity : float  Umbral de fidelidad objetivo. Default: 0.90.

        Returns
        -------
        int  — C_MAX: maximo de SWAPs antes de caer bajo target_fidelity.

        Raises
        ------
        ValueError   — Si target_fidelity cae fuera del rango fisico (B, A+B].
        RuntimeError — Si p_fit esta fuera del intervalo (0, 1).
        """
        f_min_physical = self.B_fit
        f_max_physical = self.A_fit + self.B_fit

        if not (f_min_physical < target_fidelity <= f_max_physical):
            raise ValueError(
                f"target_fidelity={target_fidelity:.4f} fuera del rango fisico "
                f"del modelo RB: ({f_min_physical:.4f}, {f_max_physical:.4f}]. "
                f"B={self.B_fit:.4f} es la asintota minima; "
                f"A+B={f_max_physical:.4f} es el maximo alcanzable."
            )

        if self.p_fit <= 0.0 or self.p_fit >= 1.0:
            raise RuntimeError(
                f"p_fit={self.p_fit:.6f} fuera del intervalo (0, 1). "
                "El ajuste RB es invalido; incrementa m_list o los shots."
            )

        # C_MAX = floor( log((F_target - B) / A) / log(p) )
        ratio = (target_fidelity - self.B_fit) / self.A_fit
        c_max = math.floor(math.log(ratio) / math.log(self.p_fit))

        print("\n" + "=" * 65)
        print("  SQTM -- Calculo Final de C_MAX (Modelo Magesan RB)")
        print("=" * 65)
        print(f"  Parametros del ajuste RB:")
        print(f"    A_fit  = {self.A_fit:.6f}  (contraste SPAM)")
        print(f"    p_fit  = {self.p_fit:.6f}  (decaimiento de proceso)")
        print(f"    B_fit  = {self.B_fit:.6f}  (asintota de mezcla, ideal=0.25)")
        print(f"\n  Error empirico purificado:")
        print(f"    r_empirico = 0.75 * (1 - p_fit) = {self.r_empirico:.6f}  "
              f"({self.r_empirico * 100:.4f} %)")
        print(f"    p_swap_teo = {self.p_swap_teorico:.6f}  "
              f"({self.p_swap_teorico * 100:.4f} %)")
        print(f"\n  Objetivo de fidelidad: F_target = {target_fidelity:.2f}  "
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
# Punto de entrada para ejecucion directa
# =============================================================================

if __name__ == "__main__":
    validator = CMaxValidator()

    # ── Fase B.1: Caracterizacion RB completa ────────────────────────────────
    m_list = [0, 1, 2, 4, 6, 8, 10, 15, 20, 25, 30]
    popt = validator.run_rb_characterization(m_list, shots=4000)

    # ── Fase B.2: Reporte de resultados y validacion del modelo ──────────────
    r_emp = validator.print_rb_results(popt)

    # ── Fase B.3: Calculo de C_MAX con fidelidad objetivo del 90 % ───────────
    c_max = validator.calculate_final_cmax(target_fidelity=0.75)
    print(f"\n[RESULTADO FINAL]  C_MAX = {c_max} SWAPs  "
          f"(r_emp = {r_emp:.4f},  p_swap_teo = {validator.p_swap_teorico:.4f})")

    # ── Fase B.4: Validacion de extrapolacion (modelo Magesan vs empirico) ───
    # Cambia 'x' para comparar el modelo ajustado contra una nueva medicion.
    x = 3
    validator.run_extrapolation_test(n=x)
    print(f"\n  Interpretacion:")
    print(f"    Si diff < 5 %, el modelo Magesan extrapola correctamente a n={x}.")
    print(f"    r_emp={r_emp:.4f}  vs  p_swap_teo={validator.p_swap_teorico:.4f}")
