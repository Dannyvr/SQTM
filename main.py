# ============================================================
# SQTM Research Project — Main Entry Point
# ============================================================

import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.comparison import run_full_comparison

# ══════════════════════════════════════════════════════════════════════════════
# Configuration Parameters
# ══════════════════════════════════════════════════════════════════════════════

# Compiler Configuration
R = 2           # Number of memory registers
n = 1           # Qubits per register (quantum word width)
c_max = 4       # Gate cost threshold
t_max_ns = 50000.0  # Time threshold (nanoseconds)

# Simulation Configuration
shots = 4000    # Number of simulation shots

# Quantum State Configuration
# Set initial_state = 0 for |0⟩ target, or 1 for |1⟩ target
initial_state = 0  # 0 = |0⟩ state, 1 = |1⟩ state

# Test Workloads
workload1 = [
    "READ_00",
    "IDLE_1",

]

workload2 = [
    "READ_00",
    "IDLE_1",
    "READ_01",
    "IDLE_1",
    "READ_00",

]

workload3 = [
    "READ_00",
    "IDLE_1",
    "READ_00",
    "IDLE_1",
    "READ_01",
    "IDLE_1",
]

workload4 = [
    "READ_00",
    "IDLE_1",
    "READ_00",
    "IDLE_1",
    "READ_01",
    "IDLE_1",
    "READ_00",
    "IDLE_1",
    "READ_00",
    "IDLE_1",
    "READ_01",
    "IDLE_1",
]

workload5 = [
    "READ_00",
    "IDLE_2",
    "READ_00",
    "IDLE_1",
    "READ_01",
    "IDLE_5",
    "READ_00",
    "IDLE_1",
    "READ_00",
    "IDLE_1",
    "READ_01",
    "IDLE_1",
    "READ_00",
    "IDLE_2",
    "READ_00",
    "IDLE_1",
    "READ_01",
    "IDLE_5",
    "READ_00",
    "IDLE_1",
    "READ_00",
    "IDLE_1",
    "READ_01",
    "IDLE_1",
]


# ══════════════════════════════════════════════════════════════════════════════
# Main Entry Point
# ══════════════════════════════════════════════════════════════════════════════

def main():
    """
    Main entry point - Execute comparative analysis with defined parameters.
    """
    print("\n" + "=" * 70)
    print("SQTM Research Project - Comparative Analysis")
    print("=" * 70)
    print(f"\n[Configuration]")
    print(f"  Memory Registers (R): {R}")
    print(f"  Qubits per Register (n): {n}")
    print(f"  Shots: {shots}")
    print(f"  Gate Cost Threshold: {c_max}")
    print(f"  Time Threshold: {t_max_ns} ns")
    state_label = "|1⟩" if initial_state == 1 else "|0⟩"
    print(f"  Target Quantum State: {state_label}")

    # Run comparative analysis with all workloads
    workloads = [
        ("Workload 1 (2 instructions)", workload1),
        ("Workload 2 (4 instructions)", workload2),
        ("Workload 3 (8 instructions)", workload3),
        ("Workload 4 (12 instructions)", workload4),
        ("Workload 5 (16 instructions)", workload5),
    ]

    print("\n[Workloads]")
    for name, _ in workloads:
        print(f"  • {name}")

    print("\n" + "=" * 70)
    print("Starting Comparative Analysis...")
    print("=" * 70)

    run_full_comparison(
        R=R,
        n=n,
        c_max=c_max,
        t_max_ns=t_max_ns,
        shots=shots,
        workloads=workloads,
        initial_state=initial_state
    )


if __name__ == "__main__":
    main()

