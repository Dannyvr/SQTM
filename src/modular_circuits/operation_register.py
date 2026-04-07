from qiskit.circuit import QuantumRegister


class OperationRegister:
    """Registro Operacional para la Systolic Quantum Teleportation Memory.

    Representa el área de trabajo activa (CPU cuántica) del sistema SQTM.
    Soporta múltiples registros operacionales identificados por reg_id.
    """

    def __init__(self, n_qubits: int = 1, reg_id: str = "") -> None:
        """Inicializa un registro operacional.

        Parameters
        ----------
        n_qubits : int, optional
            Número de qubits del registro (ancho de palabra cuántica).
            Debe ser ≥ 1. Por defecto es 1.
        reg_id : str, optional
            Identificador único del registro operacional (ej. "1", "2", "ALU").
            Por defecto es cadena vacía.

        Raises
        ------
        ValueError
            Si n_qubits < 1.
        """
        if n_qubits < 1:
            raise ValueError(f"n_qubits debe ser ≥ 1, recibido: {n_qubits}.")
        self._n_qubits: int = n_qubits
        self._reg_id: str = reg_id


    @property
    def n_qubits(self) -> int:
        """Número de qubits del registro operacional."""
        return self._n_qubits

    @property
    def reg_id(self) -> str:
        """Identificador del registro operacional."""
        return self._reg_id

    @property
    def name(self) -> str:
        """Nombre que tendrá el QuantumRegister resultante."""
        return f"Q_{self._reg_id}" if self._reg_id else "Q"


    def build(self) -> QuantumRegister:
        """Construye y devuelve el QuantumRegister operacional.

        Returns
        -------
        QuantumRegister
            Registro puro de *n_qubits* qubits con nombre ``Q`` (o
            ``Q_<reg_id>`` si se especificó un identificador).
        """
        return QuantumRegister(self._n_qubits, name=self.name)


    def __repr__(self) -> str:
        """Representación en string del registro operacional."""
        parts = [f"n_qubits={self._n_qubits}"]
        if self._reg_id:
            parts.append(f"reg_id='{self._reg_id}'")
        return f"OperationRegister({', '.join(parts)})"
