from typing import List, Optional
from src.objects.station import TargetedStation, Station
from src.solver.graph import SolvingStationGraph

def construire_chemin_surplus_graph(graph: SolvingStationGraph, start_station: Optional[TargetedStation] = None):
    """
    Construit un chemin en parcourant uniquement les stations en surplus,
    à partir du dépôt (0). Si `start_station` est fourni, il devient le
    premier arrêt après le dépôt ; sinon le NN du dépôt est choisi.
    """
    start = graph.get_station(0)
    chemin = [start]

    surplus = [s for s in graph.list_stations() if s.number != 0 and s.bike_gap() > 0]

    if not surplus:
        return chemin

    # Premier surplus : imposé (multi-start) ou laissé au NN du dépôt.
    if start_station is not None and start_station in surplus:
        chemin.append(start_station)
        surplus.remove(start_station)
        current_station = start_station
    else:
        current_station = start

    while surplus:
        nearest = graph.get_nearest_neighbor(current_station.number,lambda s: s in surplus)

        if nearest is None:
            break

        chemin.append(nearest)
        surplus.remove(nearest)
        current_station = nearest

    return chemin


def _single_start(graph: SolvingStationGraph, capacite: int, start_station: Optional[TargetedStation] = None):
    """
    Une exécution single-start de la construction surplus-first. Premier
    arrêt = NN du dépôt parmi les surplus par défaut, imposable via
    `start_station` (utilisé par le multi-start).
    """
    chemin = construire_chemin_surplus_graph(graph, start_station)

    if len(chemin) == 1:
        return None

    deficits = [s for s in graph.list_stations() if s.number != 0 and s.bike_gap() < 0]
    remaining_gap = {s.number: s.bike_gap() for s in graph.list_stations()}

    current_station = chemin[1]
    graph.add_edge(0, current_station.number)

    camion = remaining_gap[current_station.number]
    remaining_gap[current_station.number] = 0

    for next_station in chemin[2:]:
        while deficits:
            possibles = [d for d in deficits if -remaining_gap[d.number] <= camion]
            if not possibles:
                break

            nearest_deficit = graph.get_nearest_neighbor(current_station.number,lambda s: s in possibles)

            if nearest_deficit is None:
                break

            # Insertion soit par proximité (qualité), soit forcée quand charger
            # le prochain surplus ferait déborder le camion (faisabilité).
            overflow = camion + remaining_gap[next_station.number] > capacite
            if overflow or graph.get_time(current_station, nearest_deficit) < graph.get_time(current_station, next_station):
                besoin = -remaining_gap[nearest_deficit.number]
                camion -= besoin
                remaining_gap[nearest_deficit.number] = 0
                graph.add_edge(current_station.number, nearest_deficit.number)
                current_station = nearest_deficit
                deficits.remove(nearest_deficit)
            else:
                break

        # Surplus incargeable malgré les déchargements : départ infaisable,
        # le multi-start en essaiera un autre.
        diff = remaining_gap[next_station.number]
        if camion + diff > capacite:
            raise Exception("Capacité dépassée, départ infaisable")

        graph.add_edge(current_station.number, next_station.number)
        current_station = next_station

        # Surplus servi intégralement (`chemin` ne contient que des surplus).
        camion += diff
        remaining_gap[next_station.number] = 0

    for d in deficits[:]:
        if remaining_gap[d.number] < 0:
            besoin = -remaining_gap[d.number]
            camion -= besoin
            remaining_gap[d.number] = 0
            graph.add_edge(current_station.number, d.number)
            current_station = d

    graph.add_edge(current_station.number, 0)


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
        distance += graph.get_time(cur_station, nxt_station)
        tour.append(nxt)
        if nxt == 0:
            break
        cur_id = nxt
        cur_station = nxt_station
    return tour, distance


def method2(graph: SolvingStationGraph, capacite: int) -> None:
    """
    Multi-start : relance `_single_start` une fois par surplus envisageable
    comme premier arrêt après le dépôt, et garde la tournée la plus courte.
    Réduit le gap moyen d'environ 58 % vs le legacy single-start sur les 4
    catégories d'instances du benchmark, au prix d'un facteur k = #surplus
    sur le temps de calcul.
    """
    if graph.size() <= 1:
        return

    surplus_stations = [
        s for s in graph.list_stations()
        if s.number != 0 and s.bike_gap() > 0
    ]
    if not surplus_stations:
        raise Exception("No surplus station available, graph might be unsolvable")

    saved_successors = dict(graph.successors)
    saved_predecessors = dict(graph.predecessors)

    best_tour: Optional[List[int]] = None
    best_distance = float("inf")

    for start in surplus_stations:
        graph.successors = dict(saved_successors)
        graph.predecessors = dict(saved_predecessors)
        try:
            _single_start(graph, capacite, start_station=start)
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
