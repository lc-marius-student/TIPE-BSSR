from src.objects.station import TargetedStation, Station
from src.solver.map import Map, GeoPoint


class SolvingStationGraph:
    """Graphe de résolution pour le problème de rééquilibrage des vélos."""

    def __init__(self, map: Map, depot_station: Station):
        self.successors: dict[int, int | None] = {}
        self.predecessors: dict[int, int | None] = {}
        self.station_map: dict[int, TargetedStation] = {}
        self.map = map
        # Coût d'arête = temps de parcours en secondes (cf. Map.get_time, H3-H4).
        self.time_cache: dict[int, dict[int, float]] = {}

        assert depot_station.number == 0, "Depot must have number 0"
        self.add_station(TargetedStation.from_station(depot_station, 0, 0))

    def has_station(self, station_number: int) -> bool:
        return station_number in self.successors

    def add_station(self, station: TargetedStation) -> None:
        self.successors[station.number] = None
        self.predecessors[station.number] = None
        self.station_map[station.number] = station

    def get_station(self, station_number: int) -> TargetedStation:
        if not self.has_station(station_number):
            raise Exception(f"Station {station_number} does not exist")
        return self.station_map[station_number]

    def list_stations(self) -> list[TargetedStation]:
        return list(self.station_map.values())

    def remove_station(self, station_number: int) -> None:
        if not self.has_station(station_number):
            raise Exception(f"Station {station_number} does not exist")

        for number, successor in self.successors.items():
            if successor == station_number:
                self.successors[number] = None
        for number, predecessor in self.predecessors.items():
            if predecessor == station_number:
                self.predecessors[number] = None

        del self.successors[station_number]
        del self.predecessors[station_number]
        del self.station_map[station_number]

    def size(self) -> int:
        return len(self.successors)

    def list_edges(self) -> list[tuple[int, int]]:
        return [(src, dst) for src, dst in self.successors.items() if dst is not None]

    def has_edge(self, station_number1: int, station_number2: int) -> bool:
        return self.has_station(station_number1) and self.successors[station_number1] == station_number2

    def add_edge(self, station_number1: int, station_number2: int) -> None:
        if not self.has_station(station_number1):
            raise Exception(f"Station {station_number1} does not exist")
        if not self.has_station(station_number2):
            raise Exception(f"Station {station_number2} does not exist")
        if self.has_edge(station_number1, station_number2):
            raise Exception(f"Edge {station_number1} -> {station_number2} already exists")

        self.successors[station_number1] = station_number2
        self.predecessors[station_number2] = station_number1

    def remove_edge(self, station_number1: int, station_number2: int) -> None:
        if not self.has_edge(station_number1, station_number2):
            raise Exception(f"Edge {station_number1} -> {station_number2} does not exist")

        self.successors[station_number1] = None
        self.predecessors[station_number2] = None

    def get_successor(self, station_number: int) -> int | None:
        if not self.has_station(station_number):
            raise Exception(f"Station {station_number} does not exist")
        return self.successors[station_number]

    def get_predecessor(self, station_number: int) -> int | None:
        if not self.has_station(station_number):
            raise Exception(f"Station {station_number} does not exist")
        return self.predecessors[station_number]

    def is_connex(self) -> bool:
        """Vrai si chaque station a un successeur, i.e. la tournée est complète."""
        return len(self.list_edges()) == self.size()

    def get_time(self, s1: Station, s2: Station) -> float:
        """Temps de parcours routier entre deux stations, en secondes.
        """
        cache = self.time_cache.setdefault(s1.number, {})
        if s2.number not in cache:
            cache[s2.number] = self.map.get_time(
                GeoPoint(s1.lat, s1.long), GeoPoint(s2.lat, s2.long)
            )
        return cache[s2.number]

    def preload_times(self) -> None:
        """Précalcule les temps de parcours entre toutes les paires (accélère les algorithmes)."""
        stations = self.list_stations()
        for s1 in stations:
            for s2 in stations:
                if s1.number != s2.number:
                    self.get_time(s1, s2)

    def get_nearest_neighbor(self, station_number: int, condition) -> TargetedStation | None:
        """Station la plus proche (en temps) d'une station de référence satisfaisant une condition."""
        reference_station = self.get_station(station_number)

        candidates = [
            s for s in self.list_stations()
            if s.number != station_number and condition(s)
        ]
        if not candidates:
            return None

        return min(candidates, key=lambda s: self.get_time(reference_station, s))


def test():
    s0 = Station(0, "Station init", 1, "Addr 1", -1.5, 47.2)
    g = SolvingStationGraph(None, s0)

    s1 = TargetedStation(1, "Station 1", 10, "Addr 1", -1.5, 47.2, 5, 8)
    s2 = TargetedStation(2, "Station 2", 10, "Addr 2", -1.6, 47.3, 7, 4)
    s3 = TargetedStation(3, "Station 3", 10, "Addr 3", -1.7, 47.4, 2, 6)

    g.add_station(s1)
    g.add_station(s2)
    g.add_station(s3)
    assert g.size() == 4
    assert g.has_station(1)
    assert g.get_station(1) == s1

    g.add_edge(1, 2)
    g.add_edge(2, 3)
    assert len(g.list_edges()) == 2
    assert g.get_successor(1) == 2
    assert g.has_edge(1, 2)
    assert g.has_edge(2, 3)
    assert not g.has_edge(1, 3)

    g.remove_edge(1, 2)
    assert len(g.list_edges()) == 1

    g.remove_station(3)
    assert g.size() == 3
    assert len(g.list_edges()) == 0
