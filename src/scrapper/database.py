import os
import shutil
import sqlite3
from datetime import datetime

from src.objects.bike import Bike
from src.objects.station import Station


def archive_db(db_path: str):
    """Déplace la DB de la session précédente dans `<data>/archives/<timestamp>.sql`."""
    if not os.path.exists(db_path):
        return
    db_dir = os.path.dirname(db_path) or "."
    archive_dir = os.path.join(db_dir, "archives")
    os.makedirs(archive_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    archive_path = os.path.join(archive_dir, f"{timestamp}.sql")
    shutil.move(db_path, archive_path)
    print(f"Session précédente archivée → {archive_path}")


class Database:
    """SQLite local utilisé par le scrapper (écritures uniquement)."""

    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        # `station_number` est l'identifiant Bicloo natif, on l'utilise comme PK.
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS stations (
                station_number INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                capacity INTEGER NOT NULL,
                address TEXT NOT NULL DEFAULT '',
                geo_lat REAL NOT NULL,
                geo_long REAL NOT NULL
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bikes (
                bike_id TEXT PRIMARY KEY,
                number INTEGER NOT NULL
            )
        """)

        # Un mouvement = un événement ARRIVAL/DEPARTURE détecté en diffant deux
        # snapshots successifs. `source` discrimine USER / TRUCK / MAINTENANCE.
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bike_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bike_id TEXT NOT NULL,
                station_number INTEGER NOT NULL,
                movement_type TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                source TEXT NOT NULL DEFAULT 'USER',
                FOREIGN KEY (bike_id) REFERENCES bikes(bike_id),
                FOREIGN KEY (station_number) REFERENCES stations(station_number)
            )
        """)

        # Série temporelle des counts par station : alimentée à chaque changement
        # + recalage périodique sur les counts officiels (cf. Scrapper).
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS station_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                station_number INTEGER NOT NULL,
                available_bikes INTEGER NOT NULL,
                timestamp DATETIME NOT NULL,
                FOREIGN KEY (station_number) REFERENCES stations(station_number)
            )
        """)

        # Index sur (station, timestamp) : toutes les requêtes d'analyse filtrent
        # par station et trient temporellement.
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_station_history_station ON station_history(station_number, timestamp)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_bike_movements_bike_id ON bike_movements(bike_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_bike_movements_station ON bike_movements(station_number, timestamp)")

        self.conn.commit()

    def upsert_stations(self, stations: list[Station]):
        self.conn.executemany("""
            INSERT INTO stations (station_number, name, capacity, address, geo_lat, geo_long)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(station_number) DO UPDATE SET
                name = excluded.name,
                capacity = excluded.capacity,
                address = excluded.address,
                geo_lat = excluded.geo_lat,
                geo_long = excluded.geo_long
        """, [(s.number, s.name, s.capacity, s.address, s.lat, s.long) for s in stations])
        self.conn.commit()

    def upsert_bikes(self, bikes: list[Bike]):
        self.conn.executemany("""
            INSERT INTO bikes (bike_id, number)
            VALUES (?, ?)
            ON CONFLICT(bike_id) DO UPDATE SET number = excluded.number
        """, [(b.id, b.number) for b in bikes])
        self.conn.commit()

    def insert_movements_batch(self, movements: list[tuple[str, int, str, datetime, str]]):
        self.conn.executemany("""
            INSERT INTO bike_movements (bike_id, station_number, movement_type, timestamp, source)
            VALUES (?, ?, ?, ?, ?)
        """, movements)
        self.conn.commit()

    def insert_station_history_batch(self, records: list[tuple[int, int, datetime]]):
        if not records:
            return
        self.conn.executemany("""
            INSERT INTO station_history (station_number, available_bikes, timestamp)
            VALUES (?, ?, ?)
        """, records)
        self.conn.commit()
