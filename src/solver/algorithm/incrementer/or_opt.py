# =============================================================================
# Amélioration de tournée par Or-opt
# =============================================================================
#
# Voisinage complémentaire à 2-opt : on déplace un segment de 1 ≤ L ≤ 3
# stations consécutives SANS l'inverser. Capture les mouvements qu'aucune
# inversion 2-opt ne peut produire (e.g. déplacer une station vers l'autre
# bout du tour), à coût O(n²).
#
# Stratégie : first-improvement, tailles décroissantes L = 3, 2, 1
# (recommandation Or 1976 : déplacer un grand bloc avant les petits).
#
# Pré-condition : `graph.preload_distances()` doit avoir été appelé (fait
# par `solver.solve` avant tout improver). Mute le graphe en place.
# =============================================================================

from typing import Dict, List, Optional

from src.solver.graph import SolvingStationGraph


def _get_turn(graph: SolvingStationGraph) -> List[int]:
    """Tour actuel, dépôt (0) en tête, sans le retour final au dépôt."""
    turn = [0]
    current = graph.get_successor(0)
    while current is not None and current != 0:
        turn.append(current)
        current = graph.get_successor(current)
    return turn


def _relocate(turn: List[int], i: int, L: int, p: int) -> List[int]:
    """Tour après déplacement de turn[i..i+L-1] juste après la position p."""
    segment = turn[i:i + L]
    rest    = turn[:i] + turn[i + L:]
    # Dans `rest`, la position p devient p si p < i, sinon p − L (les L
    # stations du segment ont été retirées avant la position p).
    new_p = p if p < i else p - L
    return rest[:new_p + 1] + segment + rest[new_p + 1:]


def _feasible(new_turn: List[int], bike_gap_by_id: Dict[int, int], capacity: int) -> bool:
    """Charge ∈ [0, capacité] à chaque pas du nouveau tour."""
    load = 0
    for station_id in new_turn[1:]:        # on saute le dépôt en tête (charge 0)
        load += bike_gap_by_id[station_id]
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


def or_opt(graph: SolvingStationGraph, vehicle_capacity: int, max_iterations: int = 1000) -> None:
    """Or-opt first-improvement (tailles 3, 2, 1) jusqu'à l'optimum local."""
    turn = _get_turn(graph)
    n = len(turn)
    if n < 4:
        return
    distance       = graph.map_cache_distance
    bike_gap_by_id = {station_id: graph.get_station(station_id).bike_gap() for station_id in turn}

    for _ in range(max_iterations):
        improving_turn: Optional[List[int]] = None

        for L in (3, 2, 1):
            if L >= n - 1:
                continue
            for i in range(1, n - L + 1):
                t1 = turn[i - 1]
                t2 = turn[i]
                t3 = turn[i + L - 1]
                t4 = turn[i + L] if i + L < n else turn[0]

                for p in range(n):
                    if i - 1 <= p <= i + L - 1: # On ne peut pas réinsérer le segment à l'intérieur de lui-même
                        continue
                    p1 = turn[p]
                    p2 = turn[p + 1] if p + 1 < n else turn[0]

                    # On extrait turn[i..i+L-1] (= segment) et on le réinsère après turn[p] :
                    #
                    #   avant :   t1 → t2 → ... → t3 → t4    ...    p1 → p2
                    #                      └ segment ┘
                    #
                    #   après :   t1 → t4                    ...    p1 → t2 → ... → t3 → p2
                    #             └─trou─┘                          └── segment relocalisé ──┘
                    #
                    # 3 arêtes disparaissent : (t1, t2)   entrée segment
                    #                          (t3, t4)   sortie segment
                    #                          (p1, p2)   point d'insertion
                    #
                    # 3 arêtes apparaissent  : (t1, t4)   referme le trou laissé
                    #                          (p1, t2)   nouvelle entrée du segment
                    #                          (t3, p2)   nouvelle sortie du segment
                    #
                    # delta = (somme des 3 ajoutées) − (somme des 3 supprimées)
                    delta = (
                        distance[t1][t4] + distance[p1][t2] + distance[t3][p2]
                        - distance[t1][t2] - distance[t3][t4] - distance[p1][p2]
                    )
                    if delta < 0:
                        candidate = _relocate(turn, i, L, p)
                        if _feasible(candidate, bike_gap_by_id, vehicle_capacity):
                            improving_turn = candidate
                            break

                if improving_turn is not None:
                    break
            if improving_turn is not None:
                break

        if improving_turn is None:
            break
        turn = improving_turn

    _write_turn(graph, turn)
