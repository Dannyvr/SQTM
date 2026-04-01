# ============================================================
# SQTM Research Project — Systolic Work Phase Module
# Systolic Quantum Teleportation Memory
# Authors: Danny Valerio-Ramírez & Santiago Núñez-Corrales
# ============================================================

from qiskit.circuit import QuantumCircuit, QuantumRegister


class SystolicWorkPhase:


    def __init__(self, name: str = "work_phase_bus") -> None:
  
        self.name: str = name

    def apply_swap(
        self,
        qc: QuantumCircuit,
        storage_reg: QuantumRegister,
        operation_reg: QuantumRegister,
    ) -> QuantumCircuit:
        
        if storage_reg.size != operation_reg.size:
            raise ValueError(
                f"Register size mismatch: storage_reg.size={storage_reg.size} "
                f"!= operation_reg.size={operation_reg.size}. "
                "Both registers must represent the same quantum word size."
            )

        n_qubits: int = storage_reg.size

        for i in range(n_qubits):
            # SWAP decomposition using 3 CNOT gates (NISQ-level)
            qc.cx(storage_reg[i], operation_reg[i])
            qc.cx(operation_reg[i], storage_reg[i])
            qc.cx(storage_reg[i], operation_reg[i])

        return qc

    @staticmethod
    def get_cnot_cost(n_qubits: int) -> int:

        return 3 * n_qubits

    def __repr__(self) -> str:
      
        return f"SystolicWorkPhase(name='{self.name}')"
