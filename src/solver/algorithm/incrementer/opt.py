"""
Amélioration de solution par k-opt (2-opt et 3-opt).

Voisinage exhaustif (toutes les paires `(i,j)` pour 2-opt, tous les triplets
`(i,j,k)` × 7 reconnexions pour 3-opt). Stratégie first-improvement pour
2-opt et best-improvement-par-triplet pour 3-opt. Mutation in-place du
graphe.

Implémentation :
- Δ-coût en O(1) sur sommes préfixes `Fwd` / `Rev` (au lieu de resommer le
  segment à chaque candidat ; le terme `Rev[j] - Rev[i]` reste correct sur
  matrices asymétriques — vrai pour la `Map` OSM).
- Faisabilité capacité avec court-circuit sur le segment affecté via prefix
  de charge `L[k]`.
- Une seule synchronisation tour → graphe en fin d'algo.

Pré-condition : `graph.preload_distances()` doit avoir été appelé (c'est
fait par `solver.solve` avant les improvers).
"""

from typing import Dict, List, Optional, Tuple

from src.solver.graph import SolvingStationGraph


def _get_turn(graph: SolvingStationGraph) -> List[int]:
    """Tour actuel comme liste d'IDs ; dépôt (0) en tête."""
    turn: List[int] = []
    cur: Optional[int] = 0
    visited = set()
    while cur is not None and cur not in visited:
        turn.append(cur)
        visited.add(cur)
        cur = graph.get_successor(cur)
    return turn


def _prefix_sums(
    cache: Dict[int, Dict[int, float]],
    turn: List[int],
    gaps: List[int],
) -> Tuple[List[float], List[float], List[int]]:
    """
    Sommes préfixes le long du tour :
        Fwd[k] = Σ d(turn[m], turn[m+1]) pour m=0..k-1     (arcs forward)
        Rev[k] = Σ d(turn[m], turn[m-1]) pour m=1..k       (arcs reverse)
        L[k]   = Σ gaps[m]               pour m=1..k       (charge cumulée)
    `Fwd[0] = Rev[0] = L[0] = 0` — le camion démarre vide au dépôt.
    """
    n = len(turn)
    Fwd = [0.0] * n
    Rev = [0.0] * n
    L = [0] * n
    for k in range(n - 1):
        a, b = turn[k], turn[k + 1]
        Fwd[k + 1] = Fwd[k] + cache[a][b]
        Rev[k + 1] = Rev[k] + cache[b][a]
        L[k + 1] = L[k] + gaps[k + 1]
    return Fwd, Rev, L


def _sync_turn(graph: SolvingStationGraph, turn: List[int]) -> None:
    """Pose le tour dans le graphe (appelée une seule fois en fin d'algo)."""
    for (a, b) in graph.list_edges():
        graph.remove_edge(a, b)
    n = len(turn)
    for k in range(n - 1):
        graph.add_edge(turn[k], turn[k + 1])
    graph.add_edge(turn[-1], turn[0])


def _feasible_2opt(L: List[int], Q: int, i: int, j: int) -> bool:
    """
    Faisabilité capacité après inversion de `turn[i..j]`. À la nouvelle
    position `i + offset` (offset=0..j-i-1) la charge vaut
    `L[i-1] + L[j] - L[j-offset-1]`. Court-circuit au premier dépassement.
    """
    base = L[i - 1] + L[j]
    for offset in range(j - i):
        load = base - L[j - offset - 1]
        if load < 0 or load > Q:
            return False
    return True


def _feasible_tour(turn: List[int], gap_by_id: Dict[int, int], Q: int) -> bool:
    """Walk standard du tour pour faisabilité (utilisé par opt3)."""
    load = 0
    for k in range(1, len(turn)):
        load += gap_by_id[turn[k]]
        if load < 0 or load > Q:
            return False
    return True


def _apply_3opt(turn: List[int], i: int, j: int, k: int, case: int) -> List[int]:
    """
    Renvoie le tour résultant d'une des 7 reconnexions 3-opt aux coupures
    `(i, j, k)`. Segments :
        A = turn[0:i+1], B = turn[i+1:j+1],
        C = turn[j+1:k+1], D = turn[k+1:].
    """
    a = turn[0:i + 1]
    b = turn[i + 1:j + 1]
    c = turn[j + 1:k + 1]
    d = turn[k + 1:]
    if case == 1: return a + b + c[::-1] + d
    if case == 2: return a + b[::-1] + c + d
    if case == 3: return a + c + b + d
    if case == 4: return a + c[::-1] + b + d
    if case == 5: return a + c + b[::-1] + d
    if case == 6: return a + b[::-1] + c[::-1] + d
    if case == 7: return a + c[::-1] + b[::-1] + d
    raise ValueError(f"Invalid 3-opt case: {case}")


def opt2(graph: SolvingStationGraph, vehicle_capacity: int, max_iterations: int = 1000) -> None:
    """
    2-opt — inversions de segments. Pour chaque paire `(i, j)` :
        Δ = d(turn[i-1], turn[j]) + d(turn[i], turn[j+1])
            + (Rev[j] - Rev[i]) - (Fwd[j+1] - Fwd[i-1])
    Move appliqué dès qu'on en trouve un améliorant faisable
    (first-improvement). Mute le graphe en place.
    """
    turn = _get_turn(graph)
    n = len(turn)
    if n < 4:
        return
    cache = graph.map_cache_distance
    gaps = [graph.get_station(s).bike_gap() for s in turn]

    for _ in range(max_iterations):
        Fwd, Rev, L = _prefix_sums(cache, turn, gaps)
        found: Optional[Tuple[int, int]] = None

        for i in range(1, n - 2):
            ti_m1 = turn[i - 1]
            ti = turn[i]
            row_i_m1 = cache[ti_m1]
            row_i = cache[ti]
            Rev_i = Rev[i]
            Fwd_i_m1 = Fwd[i - 1]
            for j in range(i + 1, n - 1):
                tj = turn[j]
                tj_p1 = turn[j + 1]
                delta = (
                    row_i_m1[tj]
                    + row_i[tj_p1]
                    + (Rev[j] - Rev_i)
                    - (Fwd[j + 1] - Fwd_i_m1)
                )
                if delta < 0 and _feasible_2opt(L, vehicle_capacity, i, j):
                    found = (i, j)
                    break
            if found is not None:
                break

        if found is None:
            break

        i, j = found
        turn[i:j + 1] = turn[i:j + 1][::-1]
        gaps[i:j + 1] = gaps[i:j + 1][::-1]

    _sync_turn(graph, turn)


def opt3(graph: SolvingStationGraph, vehicle_capacity: int, max_iterations: int = 1000) -> None:
    """
    3-opt — 7 reconnexions par triplet `(i, j, k)`, évaluées en O(1) chacune
    via les sommes préfixes. Sélectionne au sein d'un triplet la meilleure
    reconnexion faisable (best-of-7), retourne au premier triplet améliorant.
    Mute le graphe en place.
    """
    turn = _get_turn(graph)
    n = len(turn)
    if n < 6:
        return
    cache = graph.map_cache_distance
    gaps = [graph.get_station(s).bike_gap() for s in turn]
    gap_by_id = {s.number: s.bike_gap() for s in graph.list_stations()}

    for _ in range(max_iterations):
        Fwd, Rev, _L = _prefix_sums(cache, turn, gaps)
        found: Optional[List[int]] = None

        for i in range(1, n - 3):
            ti = turn[i]
            ti_p1 = turn[i + 1]
            row_i = cache[ti]
            row_i_p1 = cache[ti_p1]
            E_AB = row_i[ti_p1]
            Fwd_i_p1 = Fwd[i + 1]
            Rev_i_p1 = Rev[i + 1]
            for j in range(i + 2, n - 2):
                tj = turn[j]
                tj_p1 = turn[j + 1]
                row_j = cache[tj]
                row_j_p1 = cache[tj_p1]
                E_BC = row_j[tj_p1]
                dB_rev = (Rev[j] - Rev_i_p1) - (Fwd[j] - Fwd_i_p1)
                Fwd_j_p1 = Fwd[j + 1]
                Rev_j_p1 = Rev[j + 1]
                for k in range(j + 2, n - 1):
                    tk = turn[k]
                    tk_p1 = turn[k + 1]
                    row_k = cache[tk]
                    E_CD = row_k[tk_p1]
                    dC_rev = (Rev[k] - Rev_j_p1) - (Fwd[k] - Fwd_j_p1)

                    boundary3 = E_AB + E_BC + E_CD
                    deltas = (
                        row_j[tk] + row_j_p1[tk_p1] - E_BC - E_CD + dC_rev,
                        row_i[tj] + row_i_p1[tj_p1] - E_AB - E_BC + dB_rev,
                        row_i[tj_p1] + row_k[ti_p1] + row_j[tk_p1] - boundary3,
                        row_i[tk] + row_j_p1[ti_p1] + row_j[tk_p1] - boundary3 + dC_rev,
                        row_i[tj_p1] + row_k[tj] + row_i_p1[tk_p1] - boundary3 + dB_rev,
                        row_i[tj] + row_i_p1[tk] + row_j_p1[tk_p1] - boundary3 + dB_rev + dC_rev,
                        row_i[tk] + row_j_p1[tj] + row_i_p1[tk_p1] - boundary3 + dB_rev + dC_rev,
                    )

                    # Best feasible improving reconnection (essais par ordre
                    # croissant de delta — on s'arrête au premier faisable).
                    case_order = sorted(range(7), key=lambda c: deltas[c])
                    for case_idx in case_order:
                        if deltas[case_idx] >= 0:
                            break
                        candidate = _apply_3opt(turn, i, j, k, case_idx + 1)
                        if _feasible_tour(candidate, gap_by_id, vehicle_capacity):
                            found = candidate
                            break

                    if found is not None:
                        break
                if found is not None:
                    break
            if found is not None:
                break

        if found is None:
            break

        turn = found
        gaps = [graph.get_station(s).bike_gap() for s in turn]

    _sync_turn(graph, turn)
