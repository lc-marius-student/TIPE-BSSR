# =============================================================================
# Iterated Local Search (ILS)
# =============================================================================
#
# Métaheuristique au-dessus du voisinage 2-opt + or-opt. Pseudocode :
#
#     s  ← solution initiale (posée par le builder en amont)
#     s  ← VND(s)                                  (descente locale initiale)
#     s* ← s                                       (incumbent = best-so-far)
#     pour _ ∈ [1, max_iterations] :
#         s'  ← perturbation(s*)                   (double-bridge ; segment
#                                                   shuffle si stagnation)
#         s'' ← VND(s')                            (intensification locale)
#         si dist(s'') < dist(s*) :
#             s* ← s''
#     retourner s*
#
# VND interne : alterne 2-opt → or-opt jusqu'à convergence locale (= aucun
# des deux ne trouve plus de mouvement améliorant).
#
# Perturbation FAIBLE : double-bridge (Martin, Otto & Felten 1991). Coupe
# le tour en 4 morceaux A B C D à 3 points aléatoires et reconnecte en
# A D C B. Mouvement 4-opt non séquentiel irréductible par 2-opt → garantit
# qu'on quitte le bassin d'attraction de l'optimum local courant.
#
# Perturbation FORTE : shuffle aléatoire d'un segment de ~30 % du tour.
# Déclenchée seulement après `stagnation_limit` itérations sans amélioration,
# pour diversifier quand le double-bridge ne suffit plus.
#
# Réf. : Cruz, Subramanian, Bruck & Iori (2016, arXiv:1605.00702) — state
# of the art sur le static bike sharing rebalancing problem.
#
# Pré-condition : `graph.preload_distances()` doit avoir été appelé ET un
# tour initial **faisable** doit être posé par un builder (`method1` ou
# `method2`). Mute le graphe en place.
# =============================================================================

import random
from typing import Dict, List

from src.solver.algorithm.incrementer.opt2 import opt2
from src.solver.algorithm.incrementer.or_opt import or_opt
from src.solver.graph import SolvingStationGraph


def _get_turn(graph: SolvingStationGraph) -> List[int]:
    """Tour actuel, dépôt (0) en tête, sans le retour final au dépôt."""
    turn = [0]
    current = graph.get_successor(0)
    while current is not None and current != 0:
        turn.append(current)
        current = graph.get_successor(current)
    return turn


def _write_turn(graph: SolvingStationGraph, turn: List[int]) -> None:
    """Réécrit le tour dans le graphe."""
    for (from_id, to_id) in graph.list_edges():
        graph.remove_edge(from_id, to_id)
    for k in range(len(turn) - 1):
        graph.add_edge(turn[k], turn[k + 1])
    graph.add_edge(turn[-1], turn[0])


def _tour_distance(turn: List[int], distance: Dict[int, Dict[int, float]]) -> float:
    """Distance totale du tour (incluant le retour final au dépôt)."""
    n = len(turn)
    return sum(distance[turn[k]][turn[k + 1]] for k in range(n - 1)) + distance[turn[-1]][turn[0]]


def _feasible(turn: List[int], gaps: Dict[int, int], capacity: int) -> bool:
    """Charge ∈ [0, capacité] à chaque pas du tour."""
    load = 0
    for station_id in turn[1:]:
        load += gaps[station_id]
        if load < 0 or load > capacity:
            return False
    return True


def _double_bridge(turn: List[int], rdm: random.Random) -> List[int]:
    """Perturbation FAIBLE : coupe le tour en A B C D à 3 points aléatoires et reconnecte en A D C B"""
    n = len(turn)
    if n < 8:
        # Tour trop court pour 3 coupures distinctes — fallback sur une
        # simple inversion d'un segment aléatoire (reste perturbant).
        i = rdm.randint(1, n - 3)
        j = rdm.randint(i + 1, n - 1)
        return turn[:i] + turn[i:j + 1][::-1] + turn[j + 1:]
    p1 = 1 + rdm.randint(0, n // 4 - 1)
    p2 = p1 + 1 + rdm.randint(0, n // 4 - 1)
    p3 = p2 + 1 + rdm.randint(0, n // 4 - 1)
    return turn[:p1] + turn[p3:] + turn[p2:p3] + turn[p1:p2]


def _random_segment_shuffle(turn: List[int], rdm: random.Random, frac: float = 0.30) -> List[int]:
    """Perturbation FORTE : permute aléatoirement un segment de `frac x n` stations"""
    n = len(turn)
    segment_length = max(2, int(frac * n))
    if segment_length >= n - 1:
        segment_length = n - 2
    i = 1 + rdm.randint(0, n - segment_length - 1)
    segment = turn[i:i + segment_length]
    rdm.shuffle(segment)
    return turn[:i] + segment + turn[i + segment_length:]


class _NoFeasiblePerturbation(Exception):
    """Levée par `_perturb_feasible` quand toutes les tentatives échouent."""


def _perturb_feasible(
    turn: List[int],
    gaps: Dict[int, int],
    capacity: int,
    rdm: random.Random,
    use_strong: bool,
    max_attempts: int = 20,
) -> List[int]:
    """Renvoie une perturbation FAISABLE de `turn`. """
    for attempt in range(max_attempts):
        if use_strong and attempt >= max_attempts // 2:
            candidate = _random_segment_shuffle(turn, rdm)
        else:
            candidate = _double_bridge(turn, rdm)
        if _feasible(candidate, gaps, capacity):
            return candidate
    raise _NoFeasiblePerturbation(f"aucune perturbation faisable après {max_attempts} tentatives")


def _vnd(graph: SolvingStationGraph, capacity: int, initial_turn: List[int]) -> List[int]:
    """VND (Variable Neighborhood Descent) : alterne 2-opt → or-opt jusqu'à convergence."""
    _write_turn(graph, initial_turn)
    distance = graph.map_cache_distance
    prev_distance = _tour_distance(initial_turn, distance)
    while True:
        opt2  (graph, capacity)
        or_opt(graph, capacity)
        current_turn = _get_turn(graph)
        new_distance = _tour_distance(current_turn, distance)
        if new_distance + 1e-9 >= prev_distance:
            return current_turn
        prev_distance = new_distance


def ils(
    graph: SolvingStationGraph,
    vehicle_capacity: int,
    max_iterations: int = 60,
    stagnation_limit: int = 15,
    seed: int = 0xBEEF,
) -> None:
    rdm            = random.Random(seed)
    distance       = graph.map_cache_distance
    bike_gap_by_id = {station.number: station.bike_gap() for station in graph.list_stations()}

    best          = _vnd(graph, vehicle_capacity, _get_turn(graph))
    best_distance = _tour_distance(best, distance)
    stagnation    = 0

    # Boucle ILS : perturbe puis VND, garde la meilleure solution rencontrée.
    for _ in range(max_iterations):
        # Si on stagne trop longtemps, on augmente la force de la perturbation pour tenter de s'échapper à un optimum local plus facilement.
        need_strong_perturbation = stagnation >= stagnation_limit

        try:
            perturbed = _perturb_feasible(
                best, bike_gap_by_id, vehicle_capacity, rdm,
                use_strong=need_strong_perturbation
            )
        except _NoFeasiblePerturbation:
            pass
        else:
            local_optimum = _vnd(graph, vehicle_capacity, perturbed)
            new_distance = _tour_distance(local_optimum, distance)
            if new_distance + 1e-9 < best_distance:
                best = local_optimum
                best_distance = new_distance
                stagnation = 0
                continue

        stagnation += 1
        if stagnation >= 2 * stagnation_limit:
            stagnation = 0

    _write_turn(graph, best)
