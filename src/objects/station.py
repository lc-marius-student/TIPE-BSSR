from dataclasses import dataclass


@dataclass
class Station:
    number: int
    name: str
    capacity: int
    address: str
    long: float
    lat: float


@dataclass
class TargetedStation(Station):
    bike_count: int
    bike_target: int

    @classmethod
    def from_station(cls, station: Station, bike_count: int, bike_target: int) -> "TargetedStation":
        return cls(station.number, station.name, station.capacity, station.address,
                   station.long, station.lat, bike_count, bike_target)

    def bike_gap(self) -> int:
        """Surplus (>0) ou déficit (<0) de vélos par rapport à la cible."""
        return self.bike_count - self.bike_target

    def is_loading(self) -> bool:
        return self.bike_gap() > 0

    def is_unloading(self) -> bool:
        return self.bike_gap() < 0
