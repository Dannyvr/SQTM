# src/modular_circuits/__init__.py
"""
SQTM Modular Circuits Package
==============================
Provides the fundamental building blocks for the
Systolic Quantum Teleportation Memory (SQTM) architecture.

Core circuit components:
    - register : SQTMRegisters – canonical register layout for one SQTM cycle.
    - operation_register : OperationRegister – quantum CPU workspace.

Note: Quantum algorithms/functions are in src.functions (e.g., SystolicTeleportation, SystolicWorkPhase)
"""

from .register import StorageRegister
from .operation_register import OperationRegister

__all__ = ["StorageRegister", "OperationRegister"]
