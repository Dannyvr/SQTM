# ============================================================
# SQTM Research Project - Comparative Analysis Module
# Compare SQTM Compiler vs SWAP Compiler
# ============================================================

import sys
import os
import random
import numpy as np
from typing import List, Tuple, Dict, Any, Optional

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.simulator.sqtm_simulator import SQTMCompiler
from src.simulator.swap_simulator import SwapCompiler


# ══════════════════════════════════════════════════════════════════════════════
# Compiler Execution Functions
# ══════════════════════════════════════════════════════════════════════════════

def run_sqtm_compiler(R: int, n: int, c_max: int, t_max_ns: float, 
                     workload: List[str], shots: int, initial_state: int = 0) -> Optional[Dict[str, Any]]:
    """
    Execute SQTM Compiler (Dual-register memory with quantum teleportation).
    
    Args:
        R: Number of memory registers
        n: Qubits per register
        c_max: Gate cost threshold
        t_max_ns: Time threshold in nanoseconds
        workload: List of instructions (READ/WRITE)
        shots: Number of simulation shots
        initial_state: Initial quantum state for fidelity (0 for |0⟩, 1 for |1⟩)
    
    Returns:
        Dictionary with simulation results
    """
    # ──────────────────────────────────────────────────────────
    # SEED INITIALIZATION - For global reproducibility
    # ──────────────────────────────────────────────────────────
    random.seed(42)
    np.random.seed(42)
    
    print("\n" + "=" * 70)
    state_label = "|1⟩" if initial_state == 1 else "|0⟩"
    print(f"SQTM Compiler - Dual-Register Memory with Quantum Teleportation")
    print(f"Target state: {state_label}")
    print("=" * 70)

    # Create compiler with initial state parameter
    sqtm = SQTMCompiler(R=R, n=n, c_max=c_max, t_max_ns=t_max_ns, initial_state=initial_state)

    # Display workload
    print(f"\n[Workload] Executing {len(workload)} instructions:")
    for i, instr in enumerate(workload, 1):
        print(f"  {i}. {instr}")

    # Compile workload
    circuit = sqtm.compile_workload(workload)

    print(f"\n[Circuit Metrics]")
    print(f"  Qubits: {circuit.num_qubits}")
    print(f"  Classical bits: {circuit.num_clbits}")
    print(f"  Depth: {circuit.depth()}")
    print(f"  Size: {circuit.size()}")

    state = sqtm.get_compiler_state()
    print(f"\n[Compiler State]")
    print(f"  Available physical qubits: {state['available_qubits']}")

    print("\n" + "-" * 70)
    print("SIMULATION PHASE")
    print("-" * 70)

    try:
        results = sqtm.run_simulation(circuit, shots=shots)
        
        print(f"\n[SQTM Results]")
        print(f"  Fidelity: {results['fidelity']:.4f}")
        print(f"  Total Shots: {results['total_shots']}")
        print(f"  Top 5 outcomes:")
        for state_str, count in list(results['counts'].items())[:5]:
            print(f"    |{state_str}⟩: {count} shots")

        return results

    except Exception as e:
        print(f"[Error] SQTM simulation failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def run_swap_compiler(R: int, n: int, c_max: int, t_max_ns: float,
                     workload: List[str], shots: int, initial_state: int = 0) -> Optional[Dict[str, Any]]:
    """
    Execute SWAP Compiler (Single-register memory, baseline comparison).
    
    Args:
        R: Number of memory registers
        n: Qubits per register
        c_max: Gate cost threshold
        t_max_ns: Time threshold in nanoseconds
        workload: List of instructions (READ/WRITE)
        shots: Number of simulation shots
        initial_state: Initial quantum state for fidelity (0 for |0⟩, 1 for |1⟩)
    
    Returns:
        Dictionary with simulation results
    """
    # ──────────────────────────────────────────────────────────
    # SEED INITIALIZATION - For global reproducibility
    # ──────────────────────────────────────────────────────────
    random.seed(42)
    np.random.seed(42)
    
    print("\n" + "=" * 70)
    state_label = "|1⟩" if initial_state == 1 else "|0⟩"
    print(f"SWAP Compiler - Single-Register Memory (Baseline)")
    print(f"Target state: {state_label}")
    print("=" * 70)

    # Create compiler with initial state parameter
    swap = SwapCompiler(R=R, n=n, c_max=c_max, t_max_ns=t_max_ns, backend_name="FakeKyiv", initial_state=initial_state)

    # Display workload
    print(f"\n[Workload] Executing {len(workload)} instructions:")
    for i, instr in enumerate(workload, 1):
        print(f"  {i}. {instr}")

    # Compile workload
    circuit = swap.compile_workload(workload)

    print(f"\n[Circuit Metrics]")
    print(f"  Qubits: {circuit.num_qubits}")
    print(f"  Classical bits: {circuit.num_clbits}")
    print(f"  Depth: {circuit.depth()}")
    print(f"  Size: {circuit.size()}")

    state = swap.get_compiler_state()
    print(f"\n[Compiler State]")
    print(f"  Available physical qubits: {state['available_qubits']}")

    print("\n" + "-" * 70)
    print("SIMULATION PHASE")
    print("-" * 70)

    try:
        results = swap.run_simulation(circuit, shots=shots)
        
        print(f"\n[SWAP Results]")
        print(f"  Fidelity: {results['fidelity']:.4f}")
        print(f"  Total Shots: {results['total_shots']}")
        print(f"  Top 5 outcomes:")
        for state_str, count in list(results['counts'].items())[:5]:
            print(f"    |{state_str}⟩: {count} shots")

        return results

    except Exception as e:
        print(f"[Error] SWAP simulation failed: {e}")
        import traceback
        traceback.print_exc()
        return None


# ══════════════════════════════════════════════════════════════════════════════
# Comparative Analysis Function
# ══════════════════════════════════════════════════════════════════════════════

def analyze_workload(R: int, n: int, c_max: int, t_max_ns: float,
                    workload_name: str, workload: List[str], shots: int, initial_state: int = 0) -> Optional[Dict[str, Any]]:
    """
    Run both compilers on a single workload and perform comparative analysis.
    
    Args:
        R: Number of memory registers
        n: Qubits per register
        c_max: Gate cost threshold
        t_max_ns: Time threshold in nanoseconds
        workload_name: Name of the workload
        workload: List of instructions
        shots: Number of simulation shots
        initial_state: Initial quantum state for fidelity (0 for |0⟩, 1 for |1⟩)
    
    Returns:
        Dictionary with comparative results
    """
    print("\n" + "█" * 70)
    print("█" + " " * 68 + "█")
    state_label = "|1⟩" if initial_state == 1 else "|0⟩"
    print("█" + f"  {workload_name} — Target: {state_label}".center(68) + "█")
    print("█" + " " * 68 + "█")
    print("█" * 70)

    # Run SQTM
    sqtm_results = run_sqtm_compiler(R=R, n=n, c_max=c_max, t_max_ns=t_max_ns,
                                     workload=workload, shots=shots, initial_state=initial_state)

    # Run SWAP
    swap_results = run_swap_compiler(R=R, n=n, c_max=c_max, t_max_ns=t_max_ns,
                                     workload=workload, shots=shots, initial_state=initial_state)

    # Comparative Analysis
    print("\n" + "=" * 70)
    print("COMPARATIVE ANALYSIS SUMMARY")
    print("=" * 70)

    if sqtm_results and swap_results:
        sqtm_fidelity = sqtm_results['fidelity']
        swap_fidelity = swap_results['fidelity']
        sqtm_qubits = sqtm_results.get('qubits', 'N/A')
        swap_qubits = swap_results.get('qubits', 'N/A')
        difference = sqtm_fidelity - swap_fidelity
        percent_diff = (difference / swap_fidelity * 100) if swap_fidelity > 0 else 0

        print(f"\n[Fidelity Comparison]")
        print(f"  SQTM:  {sqtm_fidelity:.4f} ({sqtm_fidelity*100:.2f}%)")
        print(f"  SWAP:  {swap_fidelity:.4f} ({swap_fidelity*100:.2f}%)")
        print(f"  Δ:     {difference:+.4f} ({percent_diff:+.2f}%)")

        behavior = "✓ BETTER" if difference > 0 else "✗ WORSE" if difference < 0 else "= EQUAL"
        print(f"  → SQTM is {behavior} than SWAP")

        print(f"\n[Architecture Comparison]")
        print(f"  SQTM Memory:  Dual-register (Original + Backup)")
        print(f"  SWAP Memory:  Single-register (Baseline)")
        print(f"  SQTM Resilience: Higher (backup register for redundancy)")
        print(f"  → SQTM provides resilience advantage via dual-register design")

        return {
            'workload_name': workload_name,
            'sqtm': sqtm_results,
            'swap': swap_results,
            'comparison': {
                'sqtm_fidelity': sqtm_fidelity,
                'swap_fidelity': swap_fidelity,
                'difference': difference,
                'percent_diff': percent_diff,
                'sqtm_qubits': sqtm_qubits,
                'swap_qubits': swap_qubits,
            }
        }
    else:
        print("[Error] Could not complete comparative analysis due to simulation failures")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# Full Comparison coordinator
# ══════════════════════════════════════════════════════════════════════════════

def run_full_comparison(R: int, n: int, c_max: int, t_max_ns: float,
                       shots: int, workloads: List[Tuple[str, List[str]]], initial_state: int = 0) -> None:
    """
    Execute full comparative analysis across all workloads.
    
    Args:
        R: Number of memory registers
        n: Qubits per register
        c_max: Gate cost threshold
        t_max_ns: Time threshold in nanoseconds
        shots: Number of simulation shots
        workloads: List of (name, instructions) tuples
        initial_state: Initial quantum state for fidelity (0 for |0⟩, 1 for |1⟩)
    """
    
    # Summary tracking
    results = []
    
    # Run comparative analysis for each workload
    for workload_name, workload in workloads:
        result = analyze_workload(R=R, n=n, c_max=c_max, t_max_ns=t_max_ns,
                                 workload_name=workload_name, 
                                 workload=workload, shots=shots, initial_state=initial_state)
        if result:
            results.append(result)

    # Print overall summary
    print("\n\n" + "╔" + "═" * 68 + "╗")
    print("║" + "  OVERALL COMPARATIVE SUMMARY".center(68) + "║")
    print("╚" + "═" * 68 + "╝")

    if results:
        print(f"\n[Analysis Summary - {len(results)} Workloads]")
        print("\n" + "┌" + "─" * 68 + "┐")
        
        sqtm_better_count = 0
        swap_better_count = 0
        equal_count = 0

        for result in results:
            comparison = result['comparison']
            diff = comparison['difference']
            workload = result['workload_name']

            if diff > 0:
                sqtm_better_count += 1
                status = "✓ SQTM BETTER"
            elif diff < 0:
                swap_better_count += 1
                status = "✗ SWAP BETTER"
            else:
                equal_count += 1
                status = "= EQUAL"

            print(f"│ {workload:40} → {status:20} │")

        print("└" + "─" * 68 + "┘")

        print(f"\n[Results]")
        print(f"  SQTM Better Cases:  {sqtm_better_count}/{len(results)}")
        print(f"  SWAP Better Cases:  {swap_better_count}/{len(results)}")
        print(f"  Equal Cases:        {equal_count}/{len(results)}")

        # Calculate average metrics
        avg_sqtm_fidelity = sum(r['comparison']['sqtm_fidelity'] for r in results) / len(results)
        avg_swap_fidelity = sum(r['comparison']['swap_fidelity'] for r in results) / len(results)
        avg_difference = avg_sqtm_fidelity - avg_swap_fidelity

        print(f"\n[Average Fidelity Across All Workloads]")
        print(f"  SQTM:  {avg_sqtm_fidelity:.4f} ({avg_sqtm_fidelity*100:.2f}%)")
        print(f"  SWAP:  {avg_swap_fidelity:.4f} ({avg_swap_fidelity*100:.2f}%)")
        print(f"  Δ:     {avg_difference:+.4f}")

        print("\n" + "=" * 70)
        print("✓ COMPARATIVE ANALYSIS COMPLETE")
        print("=" * 70 + "\n")

    else:
        print("\n[Error] No successful results to summarize")


if __name__ == "__main__":
    print("[Note] This module is designed to be imported from main.py")
    print("       Run 'python main.py' to execute the comparative analysis")
