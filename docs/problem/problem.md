---
title: Modélisation du problème de distribution de vélos
lang: fr
geometry: a4paper, margin=1.7cm
fontsize: 11pt
numbersections: true
header-includes:
  - \usepackage{etoolbox}
  - \usepackage{titling}
  - \setlength{\droptitle}{-7em}
  - \usepackage{titlesec}
  - \titlespacing*{\section}{0pt}{1.2ex}{0.8ex}
  - \titlespacing*{\subsection}{0pt}{0.9ex}{0.5ex}
  - \clubpenalty=10000
  - \widowpenalty=10000
  - \interlinepenalty=5000
  - \apptocmd{\normalsize}{\setlength{\abovedisplayskip}{5pt}\setlength{\belowdisplayskip}{5pt}\setlength{\abovedisplayshortskip}{5pt}\setlength{\belowdisplayshortskip}{5pt}}{}{}
---

# Description du problème

Une station peut se trouver dans l'un des **trois états** suivants :

- **Surstockée** : il y a trop de vélos.
- **Sous-stockée** : il n'y a pas assez de vélos.
- **Non considérée** : le nombre de vélos est déjà celui souhaité.

Les stations non considérées sont écartées du problème.

**Objectif :** déterminer le plus court trajet du camion permettant d'effectuer la
redistribution (chargement et déchargement) sur l'ensemble des stations considérées.

## Hypothèses de modélisation

- **Camion unique.** Un seul véhicule effectue la redistribution.
- **Tournée fermée.** Le camion réalise une unique tournée partant du dépôt et y revenant.
- **Modèle statique.** Les états des stations sont figés pendant la tournée.
- **Demande connue.** La demande de chaque station est une donnée d'entrée (le calcul des cibles est hors du périmètre de ce modèle).
- **Pas de fenêtres temporelles.** Aucune contrainte d'horaire de passage.
- **Demande bornée.** On se restreint aux instances où $|b_i| \le q/2$ pour toute station (condition suffisante de faisabilité de la tournée).

# Ensembles et données

## Ensembles

- $P = \{1, \dots, n\}$ : les sommets des $n$ stations surstockées, $n \in \mathbb{N}$.
- $D = \{n+1, \dots, n+m\}$ : les sommets des $m$ stations sous-stockées, $m \in \mathbb{N}$.
- $\{0\}$ : le sommet du dépôt.
- $V = P \cup D \cup \{0\}$ : l'ensemble des sommets considérés.
- $G = (V, A)$ : un graphe orienté complet, où $A$ est l'ensemble des arcs
  représentant les déplacements possibles du camion.

## Paramètres

- $c_{ij} \in \mathbb{R}_+$, pour tout $(i, j) \in V^2$ : la distance de la station $i$
  à la station $j$ (graphe asymétrique : $c_{ij} \ne c_{ji}$ en général).
- $q \in \mathbb{N}$ : la capacité du camion.
- $b_i \in \mathbb{Z}$, pour tout $i \in V$ : le nombre de vélos à transférer à la
  station $i$. Par convention :
  - $b_i \ge 0$ si $i \in P$ (vélos à charger dans le camion) ;
  - $b_i \le 0$ si $i \in D$ (vélos à décharger du camion) ;
  - $b_0 = 0$ (le dépôt n'a pas de demande).

## Conditions de faisabilité de l'instance

Une instance n'admet de tournée réalisable que si la somme des vélos chargés et
déchargés est nulle :

$$
\sum_{i \in P} b_i + \sum_{k \in D} b_k = 0.
$$

\newpage

# Variables de décision

- **Variable binaire de trajet**, pour tout $(i, j) \in V^2$ :

  $$
  x_{ij} =
  \begin{cases}
  1 & \text{si le camion se déplace directement de } i \text{ à } j, \\
  0 & \text{sinon.}
  \end{cases}
  $$

  On impose de plus $x_{ii} = 0$ pour tout $i \in V$ : un sommet ne peut être son
  propre successeur.

- **Variable de flux**, pour tout $(i, j) \in V^2$ : $y_{ij}$ désigne le nombre de
  vélos présents dans le camion lorsqu'il se déplace de la station $i$ à la station $j$.

  $$
  y_{ij} \in \mathbb{N} \quad \text{si } i \ne j, \qquad y_{ij} = 0 \quad \text{sinon.}
  $$

# Formulation mathématique

## Fonction objectif

On cherche à minimiser la distance totale parcourue par le camion :

$$
\min \sum_{i \in V} \sum_{j \in V} c_{ij}\, x_{ij}.
$$

## Contraintes

- **Contrainte de degré.** Chaque sommet possède exactement un successeur et un
  prédécesseur dans le trajet :

$$
\forall i \in V, \qquad \sum_{j \in V} x_{ij} = \sum_{j \in V} x_{ji} = 1.
$$

- **Élimination des sous-tours.** Aucun sous-ensemble de stations ne peut former une
  boucle fermée indépendante : pour tout $S \subseteq V \setminus \{0\}$ non vide,

$$
\sum_{i \in S} \sum_{j \in S} x_{ij} \le |S| - 1.
$$

- **Capacité du camion.** Le flux sur un arc ne peut excéder la capacité du camion,
  et n'est non nul que si l'arc est emprunté :

$$
\forall (i, j) \in V^2, \qquad y_{ij} \le q\, x_{ij}.
$$

- **Dépôt.** Le camion part et revient à vide :

$$
\forall i \in V, \qquad y_{0i} = 0 \quad \text{et} \quad y_{i0} = 0.
$$

- **Conservation du flux.** À chaque station, la variation du nombre de vélos dans
  le camion est égale à la demande $b_i$ :

$$
\forall i \in V, \qquad \sum_{j \in V} y_{ij} - \sum_{l \in V} y_{li} = b_i.
$$

\newpage

# Problème d'optimisation associé

Une instance du problème est un quadruplet $e = (G, c, q, b)$ où :

- $G = (V, A)$ est le graphe orienté complet des sommets considérés (stations et dépôt) ;
- $c : V^2 \to \mathbb{R}_+$ associe à chaque couple de sommets le coût de déplacement de l'un à l'autre ;
- $q \in \mathbb{N}$ est la capacité du camion ;
- $b : V \to \mathbb{Z}$ est la demande de chaque sommet, vérifiant les conditions de faisabilité de la partie 2.

Pour une telle instance $e$, on note $\mathrm{sol}(e)$ l'ensemble des trajets
$(x_{ij}, y_{ij})_{(i,j) \in V^2}$ satisfaisant **toutes** les contraintes de la
partie 4 (degré, élimination des sous-tours, capacité du camion, dépôt,
conservation du flux).

La distance totale parcourue est :

$$
c_e(x) = \sum_{i \in V} \sum_{j \in V} c_{ij}\, x_{ij}.
$$

**Problème de décision associé :**

\begin{flalign*}
&\quad \textsc{Bssr}_{\text{déc}} :
\begin{cases}
\textbf{Entrée} & : \ \text{une instance } e = (G, c, q, b),\ \text{un seuil } K \in \mathbb{N} \\
\textbf{Sortie} & : \ \text{existe-t-il } (x, y) \in \mathrm{sol}(e) \text{ tel que } c_e(x) \le K\ ?
\end{cases} &
\end{flalign*}

**Problème d'optimisation associé :**

\begin{flalign*}
&\quad \textsc{Bssr}_{\text{opt}} :
\begin{cases}
\textbf{Entrée} & : \ \text{une instance } e = (G, c, q, b) \\
\textbf{Sortie} & : \ \displaystyle \min_{(x, y)\, \in\, \mathrm{sol}(e)} c_e(x)
\end{cases} &
\end{flalign*}
