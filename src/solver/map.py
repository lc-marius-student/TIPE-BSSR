# =============================================================================
# Modélisation du réseau routier pour le calcul de distances et temps de trajet
# =============================================================================
#
# Hypothèses de modélisation :
#
#   H1 – Graphe routier statique
#       Le réseau routier est extrait d'OpenStreetMap via OSMnx et considéré
#       comme fixe dans le temps. On ne modélise pas les variations dynamiques
#       (travaux, routes fermées, embouteillages en temps réel).
#
#   H2 – Pas de variabilité temporelle du trafic
#       Les temps de parcours sont identiques quelle que soit l'heure de la
#       journée (pas de distinction heure de pointe / heures creuses).
#       Justification : le rééquilibrage s'effectue typiquement tôt le matin
#       ou en journée creuse, quand le trafic est relativement stable.
#
#   H3 – Facteurs de réduction de vitesse par type de voie
#       Les vitesses maximales autorisées (fournies par OSM) sont réduites par
#       un coefficient dépendant du type de route pour refléter les conditions
#       réelles de circulation d'un camion utilitaire en milieu urbain :
#           - motorway  : ×0.90  (flux fluide, peu d'arrêts)
#           - trunk     : ×0.85
#           - primary   : ×0.75  (feux, intersections fréquentes)
#           - secondary : ×0.70
#           - tertiary  : ×0.65
#           - residential : ×0.60 (stops, stationnement, manœuvres)
#           - autres    : ×0.70  (valeur prudente par défaut)
#       Justification : ces ordres de grandeur sont cohérents avec les études
#       de vitesse moyenne en milieu urbain (rapport CEREMA 2018, données TomTom
#       Traffic Index) qui montrent qu'en ville la vitesse effective représente
#       60-80 % de la vitesse autorisée selon le type de voie.
#
#   H4 – Pénalité fixe aux feux tricolores (+15 s)
#       Chaque passage par un nœud identifié comme feu de signalisation dans
#       OSM ajoute 15 secondes au temps de parcours.
#       Justification : le temps d'attente moyen à un feu urbain est estimé
#       entre 15 et 30 secondes (Webster, 1958 ; données empiriques CERTU).
#       On retient la borne basse car le camion ne s'arrête pas à chaque feu.
#
#   H5 – Plus court chemin (Dijkstra)
#       Le trajet entre deux stations est calculé comme le plus court chemin
#       sur le graphe routier pondéré. On suppose que le conducteur suit
#       toujours l'itinéraire optimal, sans détours ni erreurs de navigation.
#
# =============================================================================

import os
from dataclasses import dataclass
from datetime import datetime

import networkx as nx
import osmnx as ox


# Facteur appliqué à la vitesse autorisée selon le type de voie (cf. H3).
SPEED_FACTORS = {
    'motorway': 0.90,
    'trunk': 0.85,
    'primary': 0.75,
    'secondary': 0.70,
    'tertiary': 0.65,
    'residential': 0.60,
    'unclassified': 0.65,
}
DEFAULT_SPEED_FACTOR = 0.70
TRAFFIC_SIGNAL_PENALTY = 15  # secondes ajoutées à chaque feu tricolore (cf. H4)


def _is_traffic_signal(node_tags: dict) -> bool:
    """Vrai si le nœud OSM porte le tag `highway=traffic_signals`."""
    value = node_tags.get('highway')
    if isinstance(value, list):
        return 'traffic_signals' in value
    return value == 'traffic_signals'


def generate_sources(sources_file: str, city: str = "Nantes Métropole, France") -> nx.MultiDiGraph:
    """Construit le graphe routier OSM, applique les hypothèses H3/H4 et le met en cache sur disque."""
    g = ox.graph_from_place(city, network_type="drive")
    g = ox.add_edge_speeds(g)
    g = ox.add_edge_travel_times(g)

    g.graph['city'] = city
    g.graph['creation_date'] = datetime.now().isoformat()

    nodes = g.nodes(data=True)
    for _, dest, _, edge in g.edges(keys=True, data=True):
        if 'travel_time' not in edge:
            continue

        # H3 : la vitesse effective ne vaut qu'une fraction de la vitesse autorisée.
        highway_type = edge.get('highway')
        if isinstance(highway_type, list):
            highway_type = highway_type[0]
        edge['travel_time'] /= SPEED_FACTORS.get(highway_type, DEFAULT_SPEED_FACTOR)

        # H4 : pénalité fixe si le nœud d'arrivée de l'arête est un feu tricolore.
        if _is_traffic_signal(nodes[dest]):
            edge['travel_time'] += TRAFFIC_SIGNAL_PENALTY

    ox.save_graphml(g, sources_file)
    return g


def load_sources(sources_file: str, city: str = "Nantes Métropole, France") -> nx.MultiDiGraph:
    """Recharge un graphe mis en cache et vérifie qu'il correspond bien à la ville attendue."""
    g = ox.load_graphml(sources_file)

    if g.graph.get('city') != city:
        raise ValueError(f"Le graphe en cache concerne '{g.graph.get('city')}', et non '{city}'.")
    if g.graph.get('creation_date') is None:
        raise ValueError("Le graphe en cache n'a pas de métadonnée 'creation_date'.")

    return g


@dataclass
class GeoPoint:
    latitude: float
    longitude: float


class Map:

    def __init__(self, sources_file: str, city: str = "Nantes Métropole, France"):
        """Charge le graphe routier depuis le cache disque, ou le génère depuis OSM s'il est absent. """
        self.city = city

        if os.path.exists(sources_file):
            print("Chargement du graphe routier...")
            self.graph = load_sources(sources_file, city)
            print("Graphe chargé depuis", sources_file)
        else:
            print("Graphe absent, génération depuis OpenStreetMap...")
            self.graph = generate_sources(sources_file, city)
            print("Graphe généré et sauvegardé dans", sources_file)

        self.created_at = self.graph.graph.get('creation_date', 'unknown')
        self._node_cache: dict[tuple[float, float], int] = {}

    def _nearest_node(self, point: GeoPoint) -> int:
        """Projette un point GPS sur le nœud OSM le plus proche."""
        key = (point.latitude, point.longitude)
        if key not in self._node_cache:
            self._node_cache[key] = ox.nearest_nodes(self.graph, X=point.longitude, Y=point.latitude)
        return self._node_cache[key]

    def _shortest(self, fr: GeoPoint, to: GeoPoint, weight: str) -> float:
        """Plus court chemin entre deux points GPS, pondéré par `weight` (cf. H5, Dijkstra)."""
        return nx.shortest_path_length(
            self.graph,
            source=self._nearest_node(fr),
            target=self._nearest_node(to),
            weight=weight,
        )

    def get_time(self, fr: GeoPoint, to: GeoPoint) -> float:
        """Temps de trajet estimé entre deux points, en secondes."""
        return self._shortest(fr, to, weight='travel_time')

    def get_distance(self, fr: GeoPoint, to: GeoPoint) -> float:
        """Distance routière entre deux points, en mètres."""
        return self._shortest(fr, to, weight='length')


def test():
    map = Map("nantes_graph.graphml", city="Nantes Métropole, France")

    geo_a = GeoPoint(47.219717, -1.567036)
    geo_b = GeoPoint(47.228951, -1.556430)

    start = datetime.now()
    d = t = None
    for _ in range(100):
        d = map.get_distance(geo_a, geo_b)
        t = map.get_time(geo_a, geo_b)
    elapsed = (datetime.now() - start).total_seconds() / 100 / 2

    print("Temps de A à B :", t, "secondes (environ", t / 60, "minutes)")
    print("Distance de A à B :", d, "mètres")
    print("Calcul moyen effectué en :", elapsed, "secondes")
    print("Carte initialisée :", len(map.graph.nodes), "nœuds,",
          len(map.graph.edges), "arêtes, créée le", map.created_at)


if __name__ == "__main__":
    test()
