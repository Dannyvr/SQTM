# ============================================================
# SQTM Research Project — Qubit Mapper
# Systolic Quantum Teleportation Memory
# Authors: Danny Valerio-Ramírez & Santiago Núñez-Corrales
# Role: Quantum Compiler Architect (Senior)
# ============================================================

from typing import List, Dict, Set, Optional, Tuple
import networkx as nx


class QubitMapper:
    """
    Intelligent qubit allocation respecting hardware coupling topology.
    """

    def __init__(self, backend):
        """
        Initialize the QubitMapper.
        
        Parameters
        ----------
        backend : FakeBackend
            Qiskit backend with coupling_map and configuration.
        """
        self.backend = backend
        self.coupling_map = backend.configuration().coupling_map
        self.n_qubits = backend.configuration().n_qubits
        
        # Build connectivity graph from coupling map
        self.graph = self._build_connectivity_graph()
        
        # Track allocated qubits
        self.available_qubits: Set[int] = set(range(self.n_qubits))
        self.allocation_map: Dict[str, List[int]] = {}

    # ──────────────────────────────────────────────────────────────
    # 1. CONNECTIVITY ANALYSIS
    # ──────────────────────────────────────────────────────────────

    def _build_connectivity_graph(self) -> nx.Graph:
        """Build undirected graph from coupling_map."""
        graph = nx.Graph()
        graph.add_nodes_from(range(self.n_qubits))
        for edge in self.coupling_map:
            graph.add_edge(edge[0], edge[1])
        return graph

    # ──────────────────────────────────────────────────────────────
    # CONNECTED SUBGRAPH SEARCH
    # ──────────────────────────────────────────────────────────────

    def find_connected_subgraph(
        self, 
        size: int, 
        preferred_start: Optional[int] = None
    ) -> Optional[List[int]]:
        """Find a connected subgraph of specified size from available qubits."""
        if size > len(self.available_qubits):
            return None
        if size == 0:
            return []
        
        if preferred_start is not None and preferred_start in self.available_qubits:
            start = preferred_start
        else:
            start = min(self.available_qubits)
        
        visited = {start}
        queue = [start]
        
        while queue and len(visited) < size:
            current = queue.pop(0)
            for neighbor in self.graph.neighbors(current):
                if neighbor in self.available_qubits and neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
                    if len(visited) == size:
                        break
        
        return list(visited) if len(visited) == size else None

    def find_contiguous_block(self, size: int) -> Optional[List[int]]:
        """Find a contiguous block of connected qubits (greedy approach)."""
        available_subgraph = self.graph.subgraph(self.available_qubits).copy()
        degrees = dict(available_subgraph.degree())
        if not degrees:
            return None
        start = max(degrees, key=lambda x: degrees[x])
        return self.find_connected_subgraph(size, preferred_start=start)

    # ──────────────────────────────────────────────────────────────
    # REGISTER ALLOCATION
    # ──────────────────────────────────────────────────────────────

    def allocate_register(
        self,
        register_type: str,
        register_id: str,
        size: int,
        preferred_location: Optional[List[int]] = None
    ) -> List[int]:
        """Allocate a register to a connected subgraph."""
        if preferred_location:
            if (len(preferred_location) == size and 
                all(q in self.available_qubits for q in preferred_location)):
                subgraph = self.graph.subgraph(preferred_location)
                if nx.is_connected(subgraph):
                    allocated = preferred_location
                else:
                    allocated = self.find_connected_subgraph(size)
            else:
                allocated = self.find_connected_subgraph(size)
        else:
            allocated = self.find_connected_subgraph(size)
        
        if allocated is None:
            raise RuntimeError(
                f"[QubitMapper] Cannot allocate {size} connected qubits for {register_id}. "
                f"Only {len(self.available_qubits)} available qubits remain."
            )
        
        for qubit in allocated:
            self.available_qubits.remove(qubit)
        
        self.allocation_map[register_id] = allocated
        #print(f"[QubitMapper] Allocated {register_type} [{register_id}]: qubits {sorted(allocated)}")
        
        return allocated

    # ──────────────────────────────────────────────────────────────
    # STAR TOPOLOGY ALLOCATION (CRITICAL FOR ROUTING NOISE ISOLATION)
    # ──────────────────────────────────────────────────────────────

    def find_star_hub(self, n_leaves: int) -> Optional[int]:
        """
        Find a qubit that can serve as a hub in a star topology.
        
        Returns a qubit with at least n_leaves direct neighbors available.
        This ensures NO routing SWAPs are needed between hub and leaves.
        
        Parameters
        ----------
        n_leaves : int
            Number of leaves (neighbors) needed for the star.
        
        Returns
        -------
        Optional[int]
            Physical qubit ID of the hub, or None if no valid hub exists.
        """
        for qubit in sorted(
            self.available_qubits, 
            key=lambda q: sum(1 for n in self.graph.neighbors(q) if n in self.available_qubits),
            reverse=True
        ):
            available_neighbors = [
                n for n in self.graph.neighbors(qubit) 
                if n in self.available_qubits
            ]
            if len(available_neighbors) >= n_leaves:
                return qubit
        return None

    def allocate_star_topology(
        self,
        hub_register_id: str,
        hub_size: int,
        leaf_registers: List[Tuple[str, int]]
    ) -> Dict[str, List[int]]:
        """
        Allocate registers in a star topology to guarantee direct connectivity.
        
        Hub qubit(s) will be at the center, and all leaf registers will be 
        allocated to qubits with direct connections to the hub.
        
        This ELIMINATES routing SWAPs during transpilation with optimization_level=0.
        
        Parameters
        ----------
        hub_register_id : str
            Name of the hub register (typically the operation register).
        hub_size : int
            Number of qubits for the hub.
        leaf_registers : List[Tuple[str, int]]
            List of (register_id, size) tuples for leaf registers.
        
        Returns
        -------
        Dict[str, List[int]]
            Mapping {register_id: [physical_qubits]}.
        
        Raises
        ------
        RuntimeError
            If star topology cannot be satisfied.
        """
        result = {}
        total_leaf_qubits = sum(size for _, size in leaf_registers)
        
        # Strategy: Allocate hub first, then try to allocate leaves from hub neighbors.
        # If insufficient direct neighbors, fall back to disjoint connected components.
        
        if hub_size == 1:
            # ─ Case 1: Single-qubit hub ─
            candidates = []
            for q in sorted(self.available_qubits):
                available_neighbors = [
                    n for n in self.graph.neighbors(q)
                    if n in self.available_qubits
                ]
                if len(available_neighbors) >= total_leaf_qubits:
                    candidates.append((q, len(available_neighbors)))
            
            if not candidates:
                max_neighbors = max(
                    [len([n for n in self.graph.neighbors(q) if n in self.available_qubits]) 
                     for q in self.available_qubits], 
                    default=0
                )
                raise RuntimeError(
                    f"[QubitMapper] No qubit has {total_leaf_qubits} neighbors for leaf allocation. "
                    f"Max neighbors: {max_neighbors}"
                )
            
            hub_qubit = max(candidates, key=lambda x: x[1])[0]
            hub_qubits = [hub_qubit]
            self.available_qubits.remove(hub_qubit)
            self.allocation_map[hub_register_id] = hub_qubits
            result[hub_register_id] = hub_qubits
            print(f"[QubitMapper] Allocated hub [{hub_register_id}]: qubits {sorted(hub_qubits)}")
            hub_center = hub_qubit
            
        else:
            # ─ Case 2: Multi-qubit hub ─
            best_component = None
            for start_q in sorted(self.available_qubits):
                potential_component = self.find_connected_subgraph(hub_size, preferred_start=start_q)
                if potential_component:
                    best_component = potential_component
                    break
            
            if best_component is None:
                raise RuntimeError(
                    f"[QubitMapper] Cannot find connected {hub_size}-qubit component."
                )
            
            hub_qubits = best_component
            for q in hub_qubits:
                self.available_qubits.remove(q)
            self.allocation_map[hub_register_id] = hub_qubits
            result[hub_register_id] = hub_qubits
            print(f"[QubitMapper] Allocated hub [{hub_register_id}]: qubits {sorted(hub_qubits)}")
            
            # Find hub center (highest connectivity within hub)
            hub_subgraph = self.graph.subgraph(hub_qubits)
            if not nx.is_connected(hub_subgraph):
                raise RuntimeError(
                    f"[QubitMapper] Hub qubits {sorted(hub_qubits)} not connected."
                )
            hub_center = max(hub_qubits, key=lambda q: len([
                n for n in self.graph.neighbors(q) if n in hub_qubits
            ]))
        
        # ─ Allocate leaf registers ─
        for leaf_id, leaf_size in leaf_registers:
            # Try to allocate from hub neighbors (star topology preference)
            hub_neighbors = [
                n for n in self.graph.neighbors(hub_center)
                if n in self.available_qubits
            ]
            
            if len(hub_neighbors) >= leaf_size:
                # Sufficient direct neighbors available
                leaf_qubits = hub_neighbors[:leaf_size]
                for q in leaf_qubits:
                    self.available_qubits.remove(q)
                self.allocation_map[leaf_id] = leaf_qubits
                result[leaf_id] = leaf_qubits
                print(f"[QubitMapper] Allocated leaf [{leaf_id}]: qubits {sorted(leaf_qubits)} "
                      f"(star: neighbors of hub center {hub_center})")
            else:
                # Fallback to connected subgraph allocation
                leaf_component = self.find_connected_subgraph(leaf_size)
                if leaf_component is None:
                    raise RuntimeError(
                        f"[QubitMapper] Cannot allocate {leaf_size} connected qubits for {leaf_id}."
                    )
                
                for q in leaf_component:
                    self.available_qubits.remove(q)
                self.allocation_map[leaf_id] = leaf_component
                result[leaf_id] = leaf_component
                print(f"[QubitMapper] Allocated leaf [{leaf_id}]: qubits {sorted(leaf_component)} "
                      f"(fallback: connected subgraph)")
        
        return result

    # ──────────────────────────────────────────────────────────────
    # CHAIN TOPOLOGY ALLOCATION (SCALABLE LINEAR CHAINS)
    # ──────────────────────────────────────────────────────────────

    def _find_linear_chain(self, chain_length: int) -> Optional[List[int]]:
        """
        Find a linear chain of qubits where each qubit is connected to the next.
        
        This searches for a path: q0 — q1 — q2 — ... — q(n-1)
        where each consecutive pair (qi, qi+1) is connected.
        
        Parameters
        ----------
        chain_length : int
            Length of the chain to find.
        
        Returns
        -------
        Optional[List[int]]
            List of physical qubit IDs forming a linear chain, or None if not found.
        """
        if chain_length <= 0:
            return None
        if chain_length == 1:
            if self.available_qubits:
                return [min(self.available_qubits)]
            return None

        # Build adjacency from available qubits only
        adj = {}
        for q in self.available_qubits:
            adj[q] = set()
        
        for a, b in self.coupling_map:
            if a in self.available_qubits and b in self.available_qubits:
                adj[a].add(b)
                adj[b].add(a)

        # DFS to find a path of length chain_length
        def dfs_path(current: int, target_len: int, visited: Set[int], path: List[int]) -> Optional[List[int]]:
            """Recursive DFS to find a linear path."""
            if len(path) == target_len:
                return path.copy()
            
            for neighbor in adj.get(current, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    path.append(neighbor)
                    result = dfs_path(neighbor, target_len, visited, path)
                    if result:
                        return result
                    path.pop()
                    visited.remove(neighbor)
            
            return None

        # Try starting from each available qubit
        for start in sorted(self.available_qubits):
            visited = {start}
            path = [start]
            result = dfs_path(start, chain_length, visited, path)
            if result:
                return result

        return None

    def allocate_chain_topology(
        self,
        chain_config: List[Tuple[str, int]]
    ) -> Dict[str, List[int]]:
        """
        Allocate multiple disjoint linear chains of qubits.
        
        This is a generalized, scalable version of _get_physical_chains() from cmax_validator.
        It creates linear chains where each register occupies a contiguous segment.
        
        Topology (scalable):
            OpReg → Mem_0 → Ancilla_0 → Mem_Back_0 → Mem_1 → Ancilla_1 → Mem_Back_1 → ...
        
        Example configuration:
            chain_config = [
                ("opreg", 1),
                ("mem_0", 2),
                ("ancilla_0", 1),
                ("mem_back_0", 2),
                ("mem_1", 2),
                ("ancilla_1", 1),
                ("mem_back_1", 2),
            ]
        
        This creates a single chain of 12 qubits where:
        - First qubit: OpReg
        - Next 2: Mem_0
        - Next 1: Ancilla_0
        - Next 2: Mem_Back_0
        - And so on...
        
        Parameters
        ----------
        chain_config : List[Tuple[str, int]]
            List of (register_id, size) pairs defining the chain order.
            The total chain length is sum of all sizes.
        
        Returns
        -------
        Dict[str, List[int]]
            Mapping {register_id: [physical_qubits]} where qubits form a connected linear chain.
        
        Raises
        ------
        RuntimeError
            If a chain of the required total length cannot be found.
        """
        result = {}
        total_chain_length = sum(size for _, size in chain_config)

        print(f"\n[QubitMapper] Allocating chain topology:")
        print(f"  Total chain length: {total_chain_length} qubits")
        print(f"  Configuration: {chain_config}")

        # Find a single long chain
        chain = self._find_linear_chain(total_chain_length)
        if chain is None:
            raise RuntimeError(
                f"[QubitMapper] Cannot find linear chain of length {total_chain_length}. "
                f"Available qubits: {len(self.available_qubits)}"
            )

        print(f"  Found chain: {chain}")

        # Allocate segments of the chain to each register
        offset = 0
        for register_id, size in chain_config:
            segment = chain[offset : offset + size]
            
            # Mark these qubits as unavailable
            for q in segment:
                self.available_qubits.remove(q)
            
            self.allocation_map[register_id] = segment
            result[register_id] = segment
            
            print(f"  [{register_id:15s}] qubits {sorted(segment)} (size={size})")
            offset += size

        return result

    def allocate_multi_chain_topology(
        self,
        num_chains: int,
        chain_template: List[Tuple[str, int]],
        base_chain_length: Optional[int] = None
    ) -> Dict[str, List[int]]:
        """
        Allocate multiple identical disjoint chains (for multi-memory systems).
        
        Useful when you have multiple independent memory blocks, each with the same structure.
        
        Example:
            For 2 memory blocks with structure: Mem → Ancilla → Mem_Back
            
            chain_template = [("mem", 2), ("ancilla", 1), ("mem_back", 2)]
            allocate_multi_chain_topology(num_chains=2, chain_template=chain_template)
            
            This creates:
            - Chain 0: mem_0, ancilla_0, mem_back_0
            - Chain 1: mem_1, ancilla_1, mem_back_1
        
        Parameters
        ----------
        num_chains : int
            Number of independent chains to allocate.
        chain_template : List[Tuple[str, int]]
            Template for each chain, with register base names (without index).
        base_chain_length : Optional[int]
            If provided, adds this many qubits at the beginning of each chain.
            (E.g., for a shared OpReg hub)
        
        Returns
        -------
        Dict[str, List[int]]
            Mapping of all allocated registers (with indices in names).
        
        Raises
        ------
        RuntimeError
            If required chains cannot be found.
        """
        result = {}
        
        print(f"\n[QubitMapper] Allocating {num_chains} independent chains:")
        for chain_idx in range(num_chains):
            print(f"\n  ─ Chain {chain_idx}:")
            
            # Build this chain's configuration with indexed names
            indexed_config = []
            for base_id, size in chain_template:
                indexed_id = f"{base_id}_{chain_idx}"
                indexed_config.append((indexed_id, size))
            
            # Find and allocate the chain
            chain_length = sum(size for _, size in indexed_config)
            chain = self._find_linear_chain(chain_length)
            
            if chain is None:
                raise RuntimeError(
                    f"[QubitMapper] Cannot find chain {chain_idx} of length {chain_length}. "
                    f"Remaining available qubits: {len(self.available_qubits)}"
                )
            
            # Allocate segments
            offset = 0
            for reg_id, size in indexed_config:
                segment = chain[offset : offset + size]
                for q in segment:
                    self.available_qubits.remove(q)
                
                self.allocation_map[reg_id] = segment
                result[reg_id] = segment
                print(f"    [{reg_id:20s}] qubits {sorted(segment)}")
                offset += size
        
        return result

