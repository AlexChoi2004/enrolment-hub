import re
import shutil

import pytest

from features.accounts.seed import DEMO_EMAIL, DEMO_PASSWORD
from app import create_app
from shared import db

TOKEN_PATTERN = re.compile(r'name="csrf_token" value="([^"]+)"')


@pytest.fixture(autouse=True)
def sample_demo_and_registration_for_tests(monkeypatch):
    """The app now starts the demo student as a first-year with public sign-up off. Most tests were written around the
    two-year sample history and registering extra students, so they run with those switched on (as an
    environment setting, exactly how the real app is configured). Tests of the real defaults remove them."""
    monkeypatch.setenv("DEMO_PROFILE", "sample")
    monkeypatch.setenv("ALLOW_REGISTRATION", "1")
    monkeypatch.setenv("AI_BACKEND", "off")  # no test ever contacts a real model


@pytest.fixture(scope="session")
def template_db(tmp_path_factory):
    """The seeded database, built ONCE for the whole run. Each test gets its own copy, so tests stay independent
    but do not each pay for creating the schema and seeding about 180 subjects and their classes."""
    path = tmp_path_factory.mktemp("template") / "template.db"
    db.build_database(str(path), demo_profile="sample")
    return path


@pytest.fixture()
def conn(tmp_path, template_db):
    """A fresh, seeded SQLite connection for each test (a private copy of the template database)."""
    path = tmp_path / "test.db"
    shutil.copy(template_db, path)
    connection = db.connect(str(path))
    yield connection
    connection.close()


@pytest.fixture()
def app(tmp_path, template_db):
    shutil.copy(template_db, tmp_path / "app.db")  # create_app only builds a database if the file does not exist
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

    def do(email=DEMO_EMAIL, password=DEMO_PASSWORD, **extra):
        data = {"email": email, "password": password, "csrf_token": csrf(), **extra}
        return client.post("/login", data=data)

    return do


@pytest.fixture()
def register(client, csrf):
    """Submit the registration form. Returns the response."""

    def do(email="jane.smith@student.uni.edu.au", password="Str0ng#Pass", confirm=None, **extra):
        data = {
            "email": email,
            "password": password,
            "confirm_password": password if confirm is None else confirm,
            "csrf_token": csrf("/register"),
            **extra,
        }
        return client.post("/register", data=data)

    return do
