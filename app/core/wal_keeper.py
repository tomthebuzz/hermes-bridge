from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from ..config import settings

logger = logging.getLogger("hermes_bridge")


def board_db_path() -> Path:
    """Mirrors Hermes' layout: `default` keeps its DB at ~/.hermes/kanban.db,
    every other board at ~/.hermes/kanban/boards/<slug>/kanban.db."""
    if settings.kanban_db_path:
        return Path(settings.kanban_db_path).expanduser()
    home = Path.home() / ".hermes"
    board = settings.kanban_board or "default"
    return home / "kanban.db" if board == "default" else home / "kanban" / "boards" / board / "kanban.db"


class WalKeeper:
    """Hold one idle, query-only connection to the board DB so kanban.db-wal
    and -shm stay on disk. Without it every short-lived `hermes kanban` writer
    is the last connection, deletes them on close, and the Team Portal's
    read-only readers (which cannot recreate them) fail with "unable to open
    database file". Never writes: query_only is set before anything else."""

    def __init__(self) -> None:
        self._conn: sqlite3.Connection | None = None
        self.path = board_db_path()
        # The team store (dashboard) has the same readers and the same
        # short-lived writers (the store's CLI in Docker), so it is held too.
        self.extra_paths = [Path(settings.team_db_path).expanduser()] if settings.team_db_path else []
        self._extra: dict[Path, sqlite3.Connection] = {}

    @property
    def held(self) -> bool:
        return self._conn is not None

    @property
    def extra_held(self) -> list[str]:
        return [str(p) for p in self._extra]

    @staticmethod
    def _hold(path: Path) -> sqlite3.Connection | None:
        try:
            # mode=rw: never create a missing DB; it must already exist.
            conn = sqlite3.connect(f"file:{path}?mode=rw", uri=True, timeout=5.0, check_same_thread=False)
            conn.execute("PRAGMA query_only = 1")
            conn.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchall()
        except sqlite3.Error as e:
            logger.warning("not holding %s open (%s); Portal reads may fail between writes", path, e)
            return None
        logger.info("holding %s open to keep its WAL files", path)
        return conn

    def open(self) -> None:
        self._conn = self._hold(self.path)
        for p in self.extra_paths:
            conn = self._hold(p)
            if conn is not None:
                self._extra[p] = conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        for conn in self._extra.values():
            conn.close()
        self._extra = {}


wal_keeper = WalKeeper()
