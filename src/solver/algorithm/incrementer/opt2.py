# =============================================================================
# Amélioration de tournée par 2-opt
# =============================================================================
#
# Stratégie first-improvement : pour chaque paire d'indices (i, j) avec
# 1 ≤ i < j, on inverse le segment turn[i..j] dès qu'on trouve un mouvement
# qui réduit la distance totale ET respecte la capacité du camion.
#
# Δ-coût évalué en O(1) via sommes préfixes le long du tour (la distance
# OSM est asymétrique : inverser un segment change le coût de toutes ses
# arêtes internes). On précalcule
#
#     fwd_prefix [k] = Σ d(turn[m], turn[m+1])  pour m = 0..k-1   (forward)
#     rev_prefix [k] = Σ d(turn[m], turn[m-1])  pour m = 1..k     (reverse)
#     load_prefix[k] = Σ gap(turn[m])           pour m = 1..k     (charge)
#
# Faisabilité capacité : après l'inversion, la charge à la position i+offset
# vaut load_prefix[i-1] + load_prefix[j] − load_prefix[j-offset-1] ; on
# vérifie qu'elle reste dans [0, capacité] pour tout offset, court-circuit
# dès la première violation.
#
# Pré-condition : `graph.preload_distances()` doit avoir été appelé (fait
# par `solver.solve` avant tout improver). Mute le graphe en place.
# =============================================================================

from typing import Dict, List, Optional, Tuple

from src.solver.graph import SolvingStationGraph


def _get_turn(graph: SolvingStationGraph) -> List[int]:
    """Tour actuel, dépôt (0) en tête, sans le retour final au dépôt."""
    turn = [0]
    current = graph.get_successor(0)
    while current is not None and current != 0:
        turn.append(current)
        current = graph.get_successor(current)
    return turn


def _prefix_sums(
    distance: Dict[int, Dict[int, float]],
    turn: List[int],
    bike_gaps: List[int],
) -> Tuple[List[float], List[float], List[int]]:
    """Sommes préfixes fwd_prefix / rev_prefix / load_prefix (cf. en-tête)."""
    n = len(turn)
    fwd_prefix  = [0.0] * n
    rev_prefix  = [0.0] * n
    load_prefix = [0]   * n
    for k in range(n - 1):
        current_id = turn[k]
        next_id    = turn[k + 1]
        fwd_prefix [k + 1] = fwd_prefix [k] + distance[current_id][next_id]
        rev_prefix [k + 1] = rev_prefix [k] + distance[next_id][current_id]
        load_prefix[k + 1] = load_prefix[k] + bike_gaps[k + 1]
    return fwd_prefix, rev_prefix, load_prefix


def _feasible(load_prefix: List[int], capacity: int, i: int, j: int) -> bool:
    """Charge ∈ [0, capacité] à chaque pas après inversion de turn[i..j]."""
    pivot = load_prefix[i - 1] + load_prefix[j]
    for offset in range(j - i):
        load = pivot - load_prefix[j - offset - 1]
        if load < 0 or load > capacity:
            return False
    return True


def _write_turn(graph: SolvingStationGraph, turn: List[int]) -> None:
    """Réécrit le tour dans le graphe (appelé une seule fois en fin d'algo)."""
    for (from_id, to_id) in graph.list_edges():
        graph.remove_edge(from_id, to_id)
    for k in range(len(turn) - 1):
        graph.add_edge(turn[k], turn[k + 1])
    graph.add_edge(turn[-1], turn[0])


def opt2(graph: SolvingStationGraph, vehicle_capacity: int, max_iterations: int = 1000) -> None:
    """2-opt first-improvement jusqu'à l'optimum local."""
    turn = _get_turn(graph)
    n = len(turn)
    if n < 4:
        return
    distance  = graph.map_cache_distance
    bike_gaps = [graph.get_station(station_id).bike_gap() for station_id in turn]

    for _ in range(max_iterations):
        fwd_prefix, rev_prefix, load_prefix = _prefix_sums(distance, turn, bike_gaps)
        improving_move: Optional[Tuple[int, int]] = None

        for i in range(1, n - 2):
            for j in range(i + 1, n - 1):
                # Inversion de turn[i..j] :
                #   avant : i-1 → i → ... → j → j+1   (chaîne forward continue)
                #   après : i-1 → j → ... → i → j+1   (2 sauts + intérieur reverse)
                #
                # delta = après − avant :
                #   + d(i-1, j) + d(i, j+1)                 nouvelles frontières (sauts)
                #   + rev_prefix[j] − rev_prefix[i]         intérieur en sens reverse
                #   − (fwd_prefix[j+1] − fwd_prefix[i-1])   tout l'avant en un terme
                delta = (
                    distance[turn[i - 1]][turn[j]]
                    + distance[turn[i]][turn[j + 1]]
                    + (rev_prefix[j] - rev_prefix[i])
                    - (fwd_prefix[j + 1] - fwd_prefix[i - 1])
                )
                if delta < 0 and _feasible(load_prefix, vehicle_capacity, i, j):
                    improving_move = (i, j)
                    break
            if improving_move is not None:
                break

        if improving_move is None:
            break

        i, j = improving_move
        turn     [i:j + 1] = turn     [i:j + 1][::-1]
        bike_gaps[i:j + 1] = bike_gaps[i:j + 1][::-1]

    _write_turn(graph, turn)
