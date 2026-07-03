from pathlib import Path
from app.db import StatusDB

def test_set_and_get(tmp_path: Path):
    db = StatusDB(tmp_path / "status.db")
    db.set_status("p1", 1, "pending")
    db.set_status("p1", 1, "analyzing")
    db.set_status("p1", 2, "failed", error="timeout")
    s = db.get_statuses("p1")
    assert s[1]["status"] == "analyzing"
    assert s[2] == {"status": "failed", "error": "timeout"}
    assert db.get_statuses("p2") == {}
    db.close()

def test_persistence(tmp_path: Path):
    p = tmp_path / "status.db"
    db = StatusDB(p)
    db.set_status("p1", 1, "done")
    db.close()
    db2 = StatusDB(p)
    assert db2.get_statuses("p1")[1]["status"] == "done"
    db2.close()
