from dataclasses import dataclass

import numpy as np
from scipy.optimize import linear_sum_assignment

from src.solver.graph import SolvingStationGraph

@dataclass
class SolutionMetrics:
    solved: bool
    time: float   # secondes (temps de parcours total de la tournée)
    ratio: float  # sol / borne_inf ∈ [1, +∞).  1.0 = optimum atteint.

def assert_solution(solution: SolvingStationGraph, capacity: int):
    """
    Vérifie si le graphe donné contient une solution valide : un cycle qui
    visite toutes les stations, de bike_gap total nul, et dont la charge du
    camion reste dans [0, capacity] à chaque pas.
    """

    if not solution.is_connex():
        raise Exception("Le graphe n'est pas connexe.")

    visited = set()
    current_id = 0
    gap = 0

    while current_id is not None and current_id not in visited:
        visited.add(current_id)
        gap += solution.get_station(current_id).bike_gap()
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


def _tour_time(graph: SolvingStationGraph) -> float:
    """Temps de parcours total (secondes) du cycle hamiltonien encodé dans le graphe."""
    total = 0.0
    current_id = 0
    visited = set()

    while current_id is not None and current_id not in visited:
        visited.add(current_id)
        successor = graph.get_successor(current_id)
        if successor is not None:
            total += graph.get_time(
                graph.get_station(current_id), graph.get_station(successor)
            )
        current_id = successor

    return total


def review_solution(graph: SolvingStationGraph, capacity: int) -> SolutionMetrics:
    """Évalue une solution.

    Le score est un ratio d'approximation observé : sol / borne_inf. Comme
    borne_inf ≤ OPT, ce ratio majore le vrai ratio d'approximation (style
    p-approx). Pas besoin de la borne supérieure pour évaluer la qualité.
    """
    assert_solution(graph, capacity)

    tour_time = _tour_time(graph)
    lower_bound = compute_lower_bound(graph)

    ratio = tour_time / lower_bound if lower_bound > 0 else float('inf')

    return SolutionMetrics(time=tour_time, ratio=ratio, solved=True)


def compute_lower_bound(graph: SolvingStationGraph) -> float:
    """Borne inférieure : relaxation par problème d'affectation (cf. compute_bounds)."""
    stations = graph.list_stations()
    if len(stations) <= 1:
        return 0.0
    n = len(stations)
    cost = np.empty((n, n))
    for i, si in enumerate(stations):
        for j, sj in enumerate(stations):
            cost[i, j] = np.inf if i == j else graph.get_time(si, sj)
    rows, cols = linear_sum_assignment(cost)
    return float(cost[rows, cols].sum())


