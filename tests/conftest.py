import re

import pytest

from accounts.seed import DEMO_PASSWORD, DEMO_STUDENT_NUMBER
from app import create_app
from shared import db

TOKEN_PATTERN = re.compile(r'name="csrf_token" value="([^"]+)"')


@pytest.fixture()
def conn(tmp_path):
    """A fresh, seeded SQLite connection for each test."""
    path = tmp_path / "test.db"
    db.build_database(str(path))
    connection = db.connect(str(path))
    yield connection
    connection.close()


@pytest.fixture()
def app(tmp_path):
    return create_app(
        {"DATABASE": str(tmp_path / "app.db"), "TESTING": True, "SECRET_KEY": "test-secret-key"}
    )


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def csrf(client):
    """Fetch the CSRF token from a page, the way a browser form would carry it."""

    def fetch(path="/login"):
        html = client.get(path).get_data(as_text=True)
        return TOKEN_PATTERN.search(html).group(1)

    return fetch


@pytest.fixture()
def log_in(client, csrf):
    """Submit the login form. Returns the response."""

    def do(student_number=DEMO_STUDENT_NUMBER, password=DEMO_PASSWORD, **extra):
        data = {
            "student_number": student_number,
            "password": password,
            "csrf_token": csrf(),
            **extra,
        }
        return client.post("/login", data=data)

    return do