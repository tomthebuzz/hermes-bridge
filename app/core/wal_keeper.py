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

    @property
    def held(self) -> bool:
        return self._conn is not None

    def open(self) -> None:
        try:
            # mode=rw: never create a missing DB; the board must already exist.
            conn = sqlite3.connect(f"file:{self.path}?mode=rw", uri=True, timeout=5.0,
                                   check_same_thread=False)
            conn.execute("PRAGMA query_only = 1")
            conn.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchall()
        except sqlite3.Error as e:
            logger.warning("not holding %s open (%s); Portal reads may fail between writes", self.path, e)
            return
        self._conn = conn
        logger.info("holding %s open to keep its WAL files", self.path)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None


wal_keeper = WalKeeper()
