

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.modular_circuits.qpc import QPC


class TestQPC(unittest.TestCase):
    """Test del QPC Odómetro Híbrido con desgaste activo (gates) y pasivo (tiempo)."""

    def test_complete_bipartite_qpc_scenario(self):
        """Test del ciclo corto: desgaste activo + pasivo con evaluación unificada."""
        
        # 1. Crear QPC: 4 direcciones lógicas, C_MAX=10, T_MAX=5.0
        qpc = QPC(logical_size=4, c_max=10, t_max=5.0)
        logical_addr = 0
        
        # 2. Obtener ubicación inicial (debe ser Lado 0)
        side_initial = qpc.get_physical_location(logical_addr)
        print(f"✓ Ubicación inicial de dirección lógica {logical_addr}: Lado {side_initial}")
        self.assertEqual(side_initial, 0)
        
        # 3. Registrar operación con costo 6 y tiempo 2.0 (no alcanza C_MAX ni T_MAX)
        needs_tick_1 = qpc.update_odometer(logical_addr, gate_cost=6, time_dt=2.0)
        print(f"✓ Operación 1 (costo=6, tiempo=2.0):")
        print(f"    needs_tick={needs_tick_1}")
        print(f"    costo_acumulado={qpc.get_cost(logical_addr)}")
        print(f"    tiempo_acumulado={qpc.get_idle_time(logical_addr)}")
        self.assertFalse(needs_tick_1)  # No dispara (6 < 10 y 2.0 < 5.0)
        self.assertEqual(qpc.get_cost(logical_addr), 6)
        self.assertEqual(qpc.get_idle_time(logical_addr), 2.0)
        
        # 4. Registrar operación con costo 4 y tiempo 3.5 más (total gate=10, tiempo=5.5 >= T_MAX)
        needs_tick_2 = qpc.update_odometer(logical_addr, gate_cost=4, time_dt=3.5)
        print(f"\n✓ Operación 2 (costo=4, tiempo=3.5):")
        print(f"    needs_tick={needs_tick_2}")
        print(f"    costo_acumulado={qpc.get_cost(logical_addr)}")
        print(f"    tiempo_acumulado={qpc.get_idle_time(logical_addr)}")
        self.assertTrue(needs_tick_2)  # DISPARA (6 + 4 = 10 >= C_MAX)
        self.assertEqual(qpc.get_cost(logical_addr), 10)
        self.assertEqual(qpc.get_idle_time(logical_addr), 5.5)
        
        # 5. Llamar tick() para alternar lado y resetear AMBOS contadores
        new_side = qpc.tick(logical_addr)
        print(f"\n✓ Tick ejecutado:")
        print(f"    nuevo lado={new_side}")
        print(f"    costo reseteado a {qpc.get_cost(logical_addr)}")
        print(f"    tiempo reseteado a {qpc.get_idle_time(logical_addr)}")
        self.assertEqual(new_side, 1)  # Debe estar en Lado 1
        self.assertEqual(qpc.get_cost(logical_addr), 0)  # Costo reseteado
        self.assertEqual(qpc.get_idle_time(logical_addr), 0.0)  # Tiempo reseteado
        
        # 6. Verificar nueva ubicación y presupuesto restante (ambos)
        side_after_tick = qpc.get_physical_location(logical_addr)
        budget_remaining = qpc.get_coherence_budget_remaining(logical_addr)
        time_remaining = qpc.get_time_coherence_remaining(logical_addr)
        print(f"\n✓ Nueva ubicación y presupuestos:")
        print(f"    lado={side_after_tick}")
        print(f"    presupuesto gates={budget_remaining}/{qpc.c_max}")
        print(f"    presupuesto tiempo={time_remaining:.1f}/{qpc.t_max}")
        self.assertEqual(side_after_tick, 1)
        self.assertEqual(budget_remaining, 10)  # Presupuesto completo disponible
        self.assertEqual(time_remaining, 5.0)  # Presupuesto de tiempo completo disponible
        
        print("\n✅ Test completado exitosamente")


if __name__ == "__main__":
    unittest.main()

