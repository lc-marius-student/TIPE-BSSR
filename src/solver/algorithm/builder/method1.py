"""
Méthode 1 : plus-proche-voisin glouton (NN) avec contrainte de capacité,
en deux versions :

- `_single_start(graph, Q, start_station=None)` : NN strict, qui
  démarre par défaut sur la station chargeante la plus proche du dépôt ;
  le premier arrêt peut être imposé via `start_station`.
- `method1(graph, Q)` : multi-start NN — relance `_single_start` une fois
  par station chargeante envisageable comme premier arrêt, et conserve la
  tournée la plus courte. Bat le legacy d'environ 10 % en distance sur les
  4 catégories d'instances du benchmark, au prix d'un facteur k = #loadings
  sur le temps de calcul.
"""

from typing import List, Optional

from src.objects.station import TargetedStation
from src.solver.graph import SolvingStationGraph


def _single_start(
    graph: SolvingStationGraph,
    vehicle_capacity: int,
    start_station: Optional[TargetedStation] = None,
):
    """
    NN strict : à chaque pas, choisit le voisin le plus proche dont la visite
    garde la charge dans [0, Q].

    Si `start_station` est fourni, il remplace le choix par défaut "station
    chargeante la plus proche du dépôt" pour le premier arrêt.
    """
    if start_station is None:
        cursor_station = graph.get_nearest_neighbor(
            0, lambda s: s.number != 0 and s.is_loading()
        )
    else:
        cursor_station = start_station

    graph.add_edge(0, cursor_station.number)
    vehicle_load: int = cursor_station.bike_gap()

    for _ in range(1, graph.size() - 1):
        nearest_station: TargetedStation | None = graph.get_nearest_neighbor(
            cursor_station.number,
            lambda s:
                s.number != 0 and
                s.number != cursor_station.number and
                graph.get_predecessor(s.number) is None and
                0 <= vehicle_load + s.bike_gap() <= vehicle_capacity
        )

        if nearest_station is None:
            raise Exception("No valid successor found, graph might be unsolvable")

        graph.add_edge(cursor_station.number, nearest_station.number)
        vehicle_load += nearest_station.bike_gap()
        cursor_station = nearest_station

    graph.add_edge(cursor_station.number, 0)


def _tour_and_distance(graph: SolvingStationGraph) -> tuple[List[int], float]:
    """Lit la tournée actuelle depuis les successeurs et calcule sa distance."""
    tour = [0]
    distance = 0.0
    cur_station = graph.get_station(0)
    cur_id = 0
    while True:
        nxt = graph.get_successor(cur_id)
        if nxt is None:
            break
        nxt_station = graph.get_station(nxt)
        distance += graph.get_distance(cur_station, nxt_station)
        tour.append(nxt)
        if nxt == 0:
            break
        cur_id = nxt
        cur_station = nxt_station
    return tour, distance


def method1(graph: SolvingStationGraph, vehicle_capacity: int) -> None:
    """
    Multi-start NN : relance `_single_start` une fois par station chargeante
    en imposant celle-ci comme premier arrêt, et garde la tournée la plus
    courte.
    """
    if graph.size() <= 1:
        return

    loading_stations = [
        s for s in graph.list_stations()
        if s.number != 0 and s.is_loading()
    ]
    if not loading_stations:
        raise Exception("No loading station available, graph might be unsolvable")

    saved_successors = dict(graph.successors)
    saved_predecessors = dict(graph.predecessors)

    best_tour: Optional[List[int]] = None
    best_distance = float("inf")

    for start in loading_stations:
        graph.successors = dict(saved_successors)
        graph.predecessors = dict(saved_predecessors)
        try:
            _single_start(graph, vehicle_capacity, start_station=start)
        except Exception:
            continue
        tour, distance = _tour_and_distance(graph)
        if distance < best_distance:
            best_distance = distance
            best_tour = tour

    graph.successors = dict(saved_successors)
    graph.predecessors = dict(saved_predecessors)

    if best_tour is None:
        raise Exception("All starts failed, graph might be unsolvable")

    for i in range(len(best_tour) - 1):
        graph.add_edge(best_tour[i], best_tour[i + 1])
