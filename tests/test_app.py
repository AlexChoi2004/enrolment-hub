import os

from app import create_app


def test_health_endpoint(tmp_path):
    app = create_app({"DATABASE": str(tmp_path / "t.db"), "TESTING": True})
    res = app.test_client().get("/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok"}


def test_app_creates_and_seeds_database_when_missing(tmp_path):
    path = tmp_path / "fresh.db"
    assert not os.path.exists(path)
    create_app({"DATABASE": str(path), "TESTING": True})
    assert os.path.exists(path)