from dataclasses import dataclass

import numpy as np
from scipy.optimize import linear_sum_assignment

from src.solver.graph import SolvingStationGraph

@dataclass
class SolutionMetrics:
    """Métriques d'évaluation d'une solution"""
    solved: bool
    distance: float          # Distance totale en mètres (plus bas = mieux)
    score: float  # Score [0, 1] (plus haut = mieux)


def assert_solution(solution: SolvingStationGraph, capacity: int):
    """
    Vérifie si le graphe donné contient une solution valide : un cycle qui
    visite toutes les stations, de bike_gap total nul, et dont la charge du
    camion reste dans [0, capacity] à chaque pas.
    :param solution: Le graphe à vérifier
    :param capacity: Capacité du camion
    """

    if not solution.is_connex():
        raise Exception("Le graphe n'est pas connexe.")

    visited = set()
    current_id = 0
    gap = 0

    while current_id is not None and current_id not in visited:
        visited.add(current_id)
        gap += solution.get_station(current_id).bike_gap()
        # `gap` est la charge cumulée du camion (le dépôt a un gap nul) :
        # elle doit rester dans [0, capacity] après chaque station visitée.
        if current_id != 0 and (gap < 0 or gap > capacity):
            raise Exception(
                f"Charge du camion hors limites ({gap}) après la station {current_id}."
            )
        current_id = solution.get_successor(current_id)

    all_stations = {s.number for s in solution.list_stations() if s.number != 0}

    if gap != 0:
        raise Exception("Le graphe n'a pas un bike_gap total de 0.")

    if not all_stations.issubset(visited):
        raise Exception("Le graphe ne visite pas toutes les stations.")


def _tour_distance(graph: SolvingStationGraph) -> float:
    """Longueur du cycle hamiltonien actuellement encodé dans le graphe."""
    distance = 0.0
    current_id = 0
    visited = set()

    while current_id is not None and current_id not in visited:
        visited.add(current_id)
        successor = graph.get_successor(current_id)
        if successor is not None:
            distance += graph.get_distance(
                graph.get_station(current_id), graph.get_station(successor)
            )
        current_id = successor

    return distance


def review_solution(graph: SolvingStationGraph, capacity: int) -> SolutionMetrics:
    """
    Évalue une solution de manière détaillée
    :param graph: Le graphe avec la solution (chemin construit)
    :param capacity: Capacité du camion (nécessaire à la borne supérieure)
    :return: Métriques complètes de la solution
    """
    assert_solution(graph, capacity)

    distance = _tour_distance(graph)

    lower_bound, upper_bound = compute_bounds(graph, capacity)

    if upper_bound <= lower_bound:
        score = 1.0
    else:
        score = 1.0 - (distance - lower_bound) / (upper_bound - lower_bound)

    score = max(0.0, min(1.0, score))

    return SolutionMetrics(
        distance=distance,
        score=score,
        solved=True
    )


def compute_bounds(graph: SolvingStationGraph, capacity: int) -> tuple[float, float]:
    """
    Calcule les bornes inférieure et supérieure pour un TSP asymétrique.

    Lower bound : relaxation par problème d'affectation. On cherche la
    permutation σ (chaque station → un successeur unique, chaque station →
    un prédécesseur unique) qui minimise Σ d(i, σ(i)). C'est le TSP
    asymétrique privé de la contrainte « un seul cycle » : σ peut former
    une union de sous-tours, donc son coût minore l'optimum. Résolu en
    O(n³) par l'algorithme hongrois (`linear_sum_assignment`). La contrainte
    de capacité ne fait que restreindre l'ensemble des tournées admissibles,
    donc cette borne reste valide.

    Upper bound : coût d'une vraie tournée admissible, construite par
    plus-proche-voisin multi-départ (`method1`). Une tournée réalisable
    majore l'optimum. À défaut (aucune tournée trouvée, ou coût aberrant),
    on retombe sur 2 × lower bound.

    :param graph: Le graphe du problème
    :param capacity: Capacité du camion
    :return: (lower_bound, upper_bound)
    """
    stations = graph.list_stations()

    if len(stations) <= 1:
        return 0.0, 0.0

    n = len(stations)
    cost = np.empty((n, n))
    for i, si in enumerate(stations):
        for j, sj in enumerate(stations):
            cost[i, j] = np.inf if i == j else graph.get_distance(si, sj)

    rows, cols = linear_sum_assignment(cost)
    lower_bound = float(cost[rows, cols].sum())

    upper_bound = _nearest_neighbour_upper_bound(graph, capacity)
    if upper_bound is None or upper_bound < lower_bound:
        upper_bound = 2 * lower_bound

    return lower_bound, upper_bound


def _nearest_neighbour_upper_bound(graph: SolvingStationGraph, capacity: int) -> float | None:
    """
    Construit une tournée admissible par plus-proche-voisin multi-départ
    (`method1`) sur une copie du graphe et renvoie sa longueur. Renvoie
    None si aucune tournée n'est trouvée (instance non résolue par NN).
    """
    from src.solver.algorithm.builder.method1 import method1

    probe = SolvingStationGraph(graph.map, graph.get_station(0))
    for station in graph.list_stations():
        if station.number != 0:
            probe.add_station(station)
    probe.map_cache_distance = graph.map_cache_distance  # réutilise le cache préchargé

    try:
        method1(probe, capacity)
    except Exception:
        return None

    return _tour_distance(probe)
