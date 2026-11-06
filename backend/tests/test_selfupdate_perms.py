"""The control dir/files must stay writable by both the container (root) and the host watcher user."""

import os
import stat

os.environ.setdefault("DB_NAME", "test_db")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")

from lib import selfupdate  # noqa: E402


def test_request_creates_world_writable_control_files(tmp_path, monkeypatch):
    d = tmp_path / "control"
    monkeypatch.setattr(selfupdate, "CONTROL_DIR", d)
    monkeypatch.setattr(selfupdate, "REQUEST_FILE", d / "upgrade.request")
    monkeypatch.setattr(selfupdate, "STATUS_FILE", d / "upgrade.status")
    monkeypatch.setattr(selfupdate, "HEARTBEAT_FILE", d / "watcher.alive")
    out = selfupdate.request_upgrade("admin@example.org")
    assert out["queued"] is True
    assert stat.S_IMODE(os.stat(d).st_mode) == 0o777
    for f in ("upgrade.request", "upgrade.status"):
        assert stat.S_IMODE(os.stat(d / f).st_mode) == 0o666
    assert selfupdate.request_upgrade("x")["already"] is True
