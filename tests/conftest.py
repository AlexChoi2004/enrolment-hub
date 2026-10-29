import pytest

from shared import db


@pytest.fixture()
def conn(tmp_path):
    """A fresh, seeded SQLite connection for each test."""
    path = tmp_path / "test.db"
    db.build_database(str(path))
    connection = db.connect(str(path))
    yield connection
    connection.close()