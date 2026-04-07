

from qiskit.circuit import QuantumRegister


class StorageRegister:


    def __init__(self, n_qubits: int = 1, reg_id: str = "") -> None:
        if n_qubits < 1:
            raise ValueError(f"n_qubits debe ser ≥ 1, recibido: {n_qubits}.")
        self._n_qubits: int = n_qubits
        self._reg_id: str = reg_id

    @property
    def n_qubits(self) -> int:
        """Número de qubits del registro."""
        return self._n_qubits

    @property
    def reg_id(self) -> str:
        """Identificador opcional del nodo."""
        return self._reg_id

    @property
    def name(self) -> str:
        """Nombre que tendrá el QuantumRegister resultante."""
        return f"R_{self._reg_id}" if self._reg_id else "R"

    def build(self) -> QuantumRegister:
        """Construye y devuelve el QuantumRegister de almacenamiento.

        Returns
        -------
        QuantumRegister
            Registro puro de *n_qubits* qubits con nombre ``R`` (o
            ``R_<reg_id>`` si se especificó un identificador).
        """
        return QuantumRegister(self._n_qubits, name=self.name)


    def __repr__(self) -> str:
        parts = [f"n_qubits={self._n_qubits}"]
        if self._reg_id:
            parts.append(f"reg_id='{self._reg_id}'")
        return f"StorageRegister({', '.join(parts)})"
