# src/modular_circuits/__init__.py
"""
SQTM Modular Circuits Package
==============================
Provides the fundamental building blocks for the
Systolic Quantum Teleportation Memory (SQTM) architecture.

Phase A modules:
    - register : SQTMRegisters – canonical register layout for one SQTM cycle.
"""

from .register import StorageRegister
from .teleportation import SystolicTeleportation

__all__ = ["StorageRegister", "SystolicTeleportation"]
