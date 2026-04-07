# ============================================================
# SQTM Research Project — Systolic Teleportation Module
# Systolic Quantum Teleportation Memory
# Authors: Danny Valerio-Ramírez & Santiago Núñez-Corrales
# ============================================================

from typing import cast, Dict, Tuple
from qiskit import QuantumCircuit
from qiskit.circuit import QuantumRegister, ClassicalRegister, Clbit


class SystolicTeleportation:

    def __init__(self, name: str = "systolic_teleportation") -> None:
        """
        Initialize the Systolic Teleportation module.

        Parameters
        ----------
        name : str, optional
            Name identifier for this teleportation bus, by default "systolic_teleportation"
        """
        self.name = name
        # Cache de registros ancilla y clásicos por par lógico (source_name, dest_name)
        self._ancilla_cache: Dict[Tuple[str, str], QuantumRegister] = {}
        self._crbell_cache: Dict[Tuple[str, str], ClassicalRegister] = {}

    def build_circuit(
        self,
        qc: QuantumCircuit,
        source_reg: QuantumRegister,
        dest_reg: QuantumRegister,
    ) -> QuantumCircuit:
       
        
        # ──────────────────────────────────────────────────────────────
        # 0. VALIDATION: Ensure registers have compatible sizes
        # ──────────────────────────────────────────────────────────────
        
        N = source_reg.size
        if dest_reg.size != N:
            raise ValueError(
                f"Register size mismatch: source_reg has {N} qubits, "
                f"but dest_reg has {dest_reg.size} qubits. Must be equal."
            )
        
        # ──────────────────────────────────────────────────────────────
        # 1. GET OR CREATE BUS INTERNAL RESOURCES (Reuse on multiple calls)
        # ──────────────────────────────────────────────────────────────
        
        cache_key = (source_reg.name, dest_reg.name)
        
        if cache_key not in self._ancilla_cache:
            # PRIMERA VEZ: Crear los registros ancilla y clásico
            ancilla_name = f"ancilla_{source_reg.name}_to_{dest_reg.name}"
            cr_bell_name = f"cr_bell_{source_reg.name}_to_{dest_reg.name}"
            
            # Internal ancilla register for Bell pair generation (N qubits)
            ancilla_reg = QuantumRegister(N, name=ancilla_name)
            qc.add_register(ancilla_reg)
            self._ancilla_cache[cache_key] = ancilla_reg
            
            # Classical register for Bell measurement results (2*N bits)
            cr_bell = ClassicalRegister(2 * N, name=cr_bell_name)
            qc.add_register(cr_bell)
            self._crbell_cache[cache_key] = cr_bell
            
            print(f"[Teleportation] Created ancilla pair for {source_reg.name} -> {dest_reg.name}")
        else:
            # SIGUIENTES VECES: Reutilizar los registros existentes
            ancilla_reg = self._ancilla_cache[cache_key]
            cr_bell = self._crbell_cache[cache_key]
            
            # Reset ancilla qubits at the start of reuse
            for q in ancilla_reg:
                qc.reset(q)
            
            print(f"[Teleportation] Reusing ancilla pair for {source_reg.name} -> {dest_reg.name}")
        
        # ──────────────────────────────────────────────────────────────
        # 2. PARALLEL TELEPORTATION LOOP (over all N qubits)
        # ──────────────────────────────────────────────────────────────
        
        for i in range(N):
            source_q = source_reg[i]
            dest_q = dest_reg[i]
            link_q = ancilla_reg[i]
            
            # ────────────────────────────────────────────────────────
            # 2a. BELL CHANNEL GENERATION (between link_q and dest_q)
            # ────────────────────────────────────────────────────────
            
            qc.h(link_q)
            qc.cx(link_q, dest_q)
            
            # ────────────────────────────────────────────────────────
            # 2b. SOURCE INTERACTION (BSM preparation)
            # ────────────────────────────────────────────────────────
            
            qc.cx(source_q, link_q)
            qc.h(source_q)
            
            # ────────────────────────────────────────────────────────
            # 2c. BELL STATE MEASUREMENT (BSM)
            # Classical bits: cr_bell[2*i] = source_q, cr_bell[2*i+1] = link_q
            # ────────────────────────────────────────────────────────
            
            qc.measure(source_q, cr_bell[2 * i])
            qc.measure(link_q, cr_bell[2 * i + 1])
            
            # ────────────────────────────────────────────────────────
            # 2d. FEED-FORWARD (Data Movement Correction)
            # ────────────────────────────────────────────────────────
            
            # If cr_bell[2*i+1] == 1 (bit position 2*i+1), apply X
            with qc.if_test((cast(Clbit, cr_bell[2 * i + 1]), 1)):
                qc.x(dest_q)
            
            # If cr_bell[2*i] == 1 (bit position 2*i), apply Z
            with qc.if_test((cast(Clbit, cr_bell[2 * i]), 1)):
                qc.z(dest_q)
            
            # ────────────────────────────────────────────────────────
            # 2e. ACTIVE RESET (Clean source and ancilla, NOT destination)
            # ────────────────────────────────────────────────────────
            
            qc.reset(source_q)
            qc.reset(link_q)
        
        return qc

    def __repr__(self) -> str:
        """String representation of the Systolic Teleportation module."""
        return f"{self.__class__.__name__}(name='{self.name}')"
