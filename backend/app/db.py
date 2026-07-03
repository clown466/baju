import sqlite3
import threading
from pathlib import Path


class StatusDB:
    """每集扒剧状态，用于断点续跑。单文件 SQLite，线程安全。"""

    def __init__(self, path: Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS episode_status ("
                " project_id TEXT NOT NULL,"
                " episode INTEGER NOT NULL,"
                " status TEXT NOT NULL,"
                " error TEXT NOT NULL DEFAULT '',"
                " PRIMARY KEY (project_id, episode))"
            )
            self._conn.commit()

    def set_status(self, pid: str, ep: int, status: str, error: str = "") -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO episode_status (project_id, episode, status, error)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(project_id, episode)"
                " DO UPDATE SET status=excluded.status, error=excluded.error",
                (pid, ep, status, error),
            )
            self._conn.commit()

    def get_statuses(self, pid: str) -> dict[int, dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT episode, status, error FROM episode_status"
                " WHERE project_id=?", (pid,),
            ).fetchall()
        return {ep: {"status": st, "error": err} for ep, st, err in rows}

    def close(self) -> None:
        self._conn.close()
