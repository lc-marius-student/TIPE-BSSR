# =============================================================================
# Stock cible d'une station Bicloo (modèle de Skellam, problème newsvendor)
# =============================================================================
#
# Modélisation, sur un intervalle de temps dt :
#
#   - les arrivées de vélos suivent une loi de Poisson(λ_in)
#   - les départs suivent une loi de Poisson(λ_out)
#   - on suppose les deux indépendantes. C'est exact en régime non saturé :
#     les deux processus sont alors causalement découplés. Aux saturations
#     (station pleine ou vide), une corrélation locale apparaît mécaniquement
#     — la fréquence des saturations sur les données réelles est à mesurer
#     pour quantifier le biais résiduel.
#
# La variation nette du stock Δ = #arrivées − #départs suit alors une loi de
# Skellam(λ_in, λ_out). Pour un stock initial b_t ∈ [0, capacity], le stock
# final est b_t + Δ. On pénalise les états hors capacité :
#
#       pénalité(b) = β_empty · max(−b, 0)  +  β_full · max(b − capacity, 0)
#
# Le stock cible optimal b* est celui qui minimise l'espérance de pénalité —
# c'est un problème de type "newsvendor" à une seule période.
#
# La loi de Skellam est de support infini ; on la tronque à [−S, +S] avec S
# grand devant λ_in + λ_out. La probabilité tombée hors support est alors
# négligeable et l'erreur sur l'espérance reste très inférieure à la précision
# d'estimation des λ.
#
# Régime de validité : b* ∈ ]0, capacity[.
# =============================================================================

import numpy as np
from scipy.stats import skellam


def penalty(b: int, capacity: int, beta_empty: float, beta_full: float) -> float:
    if b < 0:
        return -b * beta_empty
    elif b > capacity:
        return (b - capacity) * beta_full
    else:
        return 0.0


def expected_penalty(b_t: int, capacity: int, lambda_in: float, lambda_out: float,
                     beta_empty: float, beta_full: float, support: int) -> float:
    delta = np.arange(-support, support + 1)
    probs = skellam.pmf(delta, lambda_in, lambda_out)
    stocks = b_t + delta

    total_penalty = 0.0
    for b, p in zip(stocks, probs):
        total_penalty += float(p) * penalty(int(b), capacity, beta_empty, beta_full)

    return total_penalty


def compute_target(capacity: int, lambda_in: float, lambda_out: float,
                   beta_empty: float = 2.0, beta_full: float = 1.0,
                   support: int = 25) -> list[float]:
    return [expected_penalty(b, capacity, lambda_in, lambda_out, beta_empty, beta_full, support)
            for b in range(capacity + 1)]

if __name__ == "__main__":
    capacity, lambda_in, lambda_out = 18, 5, 7
    z = compute_target(capacity, lambda_in, lambda_out)
    b_star = int(np.argmin(z))

    print("===== TABLEAU DES PÉNALITÉS (modèle de Skellam) =====")
    print(f"capacity={capacity}, λ_in={lambda_in}, λ_out={lambda_out}")
    for b, zb in enumerate(z):
        marker = " <--- OPTIMAL" if b == b_star else ""
        print(f"b = {b:2d}  |  E[Z] = {zb:.4f}{marker}")
