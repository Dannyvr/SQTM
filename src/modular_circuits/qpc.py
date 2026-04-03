
class QPC:
    """
    Odómetro Híbrido para Quantum Ping-Pong Cuántico (QPC).
    Rastrea tanto desgaste activo (compuertas) como pasivo (tiempo).
    """

    def __init__(self, logical_size: int, c_max: int, t_max: float) -> None:
        """
        Inicializa el controlador BipartiteQPC.
        
        Args:
            logical_size: Número de direcciones lógicas
            c_max: Umbral máximo de costo térmico (desgaste activo - gates)
            t_max: Umbral máximo de tiempo inactivo (desgaste pasivo - tiempo)
        """
        self.logical_size = logical_size
        self.c_max = c_max
        self.t_max = t_max
        
        # Lado activo por dirección lógica: 0 (Lado A) o 1 (Lado B)
        self._active_side = {i: 0 for i in range(logical_size)}
        
        # Costo térmico acumulado por dirección lógica (desgaste activo)
        self._costs = {i: 0 for i in range(logical_size)}
        
        # Tiempo inactivo acumulado por dirección lógica (desgaste pasivo)
        self._idle_times = {i: 0.0 for i in range(logical_size)}

    def get_physical_location(self, logical_address: int) -> int:
        """Retorna el lado físico activo para una dirección lógica."""
        if logical_address < 0 or logical_address >= self.logical_size:
            raise ValueError(f"Dirección lógica {logical_address} fuera de rango [0, {self.logical_size - 1}]")
        
        return self._active_side[logical_address]

    def update_odometer(self, logical_address: int, gate_cost: int = 0, time_dt: float = 0.0) -> bool:
        """
        Actualiza el odómetro híbrido (desgaste activo + pasivo).
        
        Args:
            logical_address: Dirección lógica de la memoria
            gate_cost: Costo térmico de las compuertas (desgaste activo)
            time_dt: Tiempo transcurrido en inactividad (desgaste pasivo)
        
        Returns:
            True si CUALQUIERA de los umbrales se alcanzó o superó, False en caso contrario.
        """
        if logical_address < 0 or logical_address >= self.logical_size:
            raise ValueError(f"Dirección lógica {logical_address} fuera de rango [0, {self.logical_size - 1}]")
        
        # Acumular desgaste activo (gates)
        self._costs[logical_address] += gate_cost
        
        # Acumular desgaste pasivo (tiempo inactivo)
        self._idle_times[logical_address] += time_dt
        
        # Evaluar ambos umbrales: retorna True si CUALQUIERA se alcanza o supera
        if self._costs[logical_address] >= self.c_max or self._idle_times[logical_address] >= self.t_max:
            return True  # Requiere tele-refresco
        
        return False

    def tick(self, logical_address: int) -> int:
        """
        Ejecuta un tele-refresco: alterna el lado activo y resetea el odómetro.
        
        Args:
            logical_address: Dirección lógica de la memoria
        
        Returns:
            El nuevo lado activo (0 o 1)
        """
        if logical_address < 0 or logical_address >= self.logical_size:
            raise ValueError(f"Dirección lógica {logical_address} fuera de rango [0, {self.logical_size - 1}]")
        
        # Alternar lado: 0 -> 1, 1 -> 0
        self._active_side[logical_address] = 1 - self._active_side[logical_address]
        
        # Resetear AMBOS contadores del odómetro en el lado antiguo
        self._costs[logical_address] = 0
        self._idle_times[logical_address] = 0.0
        
        return self._active_side[logical_address]

    # ==================== Métodos de Inspección ====================

    def get_cost(self, logical_address: int) -> int:
        """Retorna el costo térmico acumulado (desgaste activo) de una dirección lógica."""
        if logical_address < 0 or logical_address >= self.logical_size:
            raise ValueError(f"Dirección lógica {logical_address} fuera de rango [0, {self.logical_size - 1}]")
        return self._costs[logical_address]

    def get_idle_time(self, logical_address: int) -> float:
        """Retorna el tiempo inactivo acumulado (desgaste pasivo) de una dirección lógica."""
        if logical_address < 0 or logical_address >= self.logical_size:
            raise ValueError(f"Dirección lógica {logical_address} fuera de rango [0, {self.logical_size - 1}]")
        return self._idle_times[logical_address]

    def get_coherence_budget_remaining(self, logical_address: int) -> int:
        """Retorna el presupuesto restante antes de decoherencia (desgaste activo)."""
        if logical_address < 0 or logical_address >= self.logical_size:
            raise ValueError(f"Dirección lógica {logical_address} fuera de rango [0, {self.logical_size - 1}]")
        return max(0, self.c_max - self._costs[logical_address])

    def get_time_coherence_remaining(self, logical_address: int) -> float:
        """Retorna el presupuesto de tiempo restante antes de decoherencia (desgaste pasivo)."""
        if logical_address < 0 or logical_address >= self.logical_size:
            raise ValueError(f"Dirección lógica {logical_address} fuera de rango [0, {self.logical_size - 1}]")
        return max(0.0, self.t_max - self._idle_times[logical_address])
