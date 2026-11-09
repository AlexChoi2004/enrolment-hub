"""The security and ethics documents make claims about the code. These tests keep those claims true: every file and test they name must exist, and
the few settings they quote (lockout, password length, cookie flags, headers, secrets) must still have those values."""
import glob
import re
from pathlib import Path

import pytest

from app import create_app
from features.accounts import service as accounts
from shared import db, security

ROOT = Path(__file__).resolve().parents[1]
DOCS = [ROOT / "docs" / "SECURITY.md", ROOT / "docs" / "ETHICS.md"]
CODE_EXTENSIONS = (".py", ".html", ".yml", ".sql", ".json", ".md", ".ts", ".tsx", ".example", ".gitignore")


def backticked(path):
    return re.findall(r"`([^`\n]+)`", path.read_text(encoding="utf-8"))


def test_every_test_the_documents_name_exists():
    missing = []
    for doc in DOCS:
        for token in backticked(doc):
            if "::" not in token or not token.startswith("tests/"):
                continue
            file, name = token.split("::", 1)
            target = ROOT / file
            if not target.exists() or not re.search(rf"^\s*def {re.escape(name)}\(", target.read_text(encoding="utf-8"), re.M):
                missing.append(f"{doc.name}: {token}")
    assert missing == []


def test_every_file_the_documents_name_exists():
    missing = []
    for doc in DOCS:
        for token in backticked(doc):
            token = token.split(" ")[0].split("::")[0]
            if "/" not in token and not token.endswith(CODE_EXTENSIONS):
                continue
            if token.startswith(("http", "/", "-", "$", "python", "npm", "ruff", "pip", "cd ", "git ")) or " " in token or token.endswith(("/", "...")):
                continue
            if not token.endswith(CODE_EXTENSIONS) and not (ROOT / token).is_dir():
                continue
            if not (glob.glob(str(ROOT / token)) or (ROOT / token).exists()):
                missing.append(f"{doc.name}: {token}")
    assert missing == []


def test_the_named_functions_and_settings_still_exist():
    expected = {
        "shared/security.py": ["csrf_valid", "require_csrf", "safe_next", "apply_security_headers", "login_required"],
        "features/accounts/service.py": ["password_problems", "MAX_FAILED_LOGINS", "LOCKOUT_SECONDS"],
        "features/simulator/routes.py": ["_demo_only"],
    }
    for file, names in expected.items():
        text = (ROOT / file).read_text(encoding="utf-8")
        assert all(name in text for name in names), file


def test_the_documented_account_rules_have_the_documented_values():
    assert (accounts.MIN_PASSWORD_LENGTH, accounts.MAX_FAILED_LOGINS, accounts.LOCKOUT_SECONDS) == (8, 5, 300)
    assert accounts.password_problems("Abcdef1!") == [] and len(accounts.password_problems("abcdefgh")) == 3  # no capital, number or special character


def test_the_documented_headers_are_the_ones_sent():
    csp = security.CONTENT_SECURITY_POLICY
    assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp and "unsafe-inline" not in csp and "unsafe-eval" not in csp


def test_the_session_cookie_settings_match_this_document(tmp_path, monkeypatch):
    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    app = create_app({"DATABASE": str(tmp_path / "a.db")})
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True and app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert app.config["PERMANENT_SESSION_LIFETIME"].total_seconds() == 2 * 3600 and app.config["SESSION_COOKIE_SECURE"] is False  # opt-in, as the gaps list says
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "1")
    assert create_app({"DATABASE": str(tmp_path / "b.db")}).config["SESSION_COOKIE_SECURE"] is True


def test_the_secret_key_comes_from_the_environment_and_secrets_are_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "from-the-environment")
    assert create_app({"DATABASE": str(tmp_path / "a.db")}).config["SECRET_KEY"] == "from-the-environment"
    monkeypatch.delenv("SECRET_KEY")
    first, second = (create_app({"DATABASE": str(tmp_path / f"{n}.db")}).config["SECRET_KEY"] for n in ("c", "d"))
    assert first != second and len(first) >= 32  # random for each start when none is set
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in ignored and "*.db" in ignored
    assert (ROOT / ".env.example").read_text(encoding="utf-8").strip().splitlines()[-1] == "SECRET_KEY=change-me"  # names only, no real secret


def test_registration_is_off_unless_switched_on(tmp_path, monkeypatch):
    monkeypatch.delenv("ALLOW_REGISTRATION", raising=False)
    assert create_app({"DATABASE": str(tmp_path / "a.db")}).config["ALLOW_REGISTRATION"] is False
    monkeypatch.setenv("ALLOW_REGISTRATION", "1")
    assert create_app({"DATABASE": str(tmp_path / "b.db")}).config["ALLOW_REGISTRATION"] is True


def test_the_ethics_note_describes_the_invented_electives_correctly(tmp_path):
    path = tmp_path / "t.db"
    db.build_database(str(path), demo_profile="fresh")
    conn = db.connect(str(path))
    codes = sorted(r[0] for r in conn.execute("SELECT code FROM subjects WHERE is_synthetic = 1"))
    assert codes == [f"SYN{n}" for n in range(101, 113)]
    assert all(r[0] is None for r in conn.execute("SELECT handbook_url FROM subjects WHERE is_synthetic = 1"))  # no Handbook link for invented subjects


def test_the_two_descriptions_the_ethics_note_flags_really_mention_indigenous_topics(tmp_path):
    path = tmp_path / "t.db"
    db.build_database(str(path), demo_profile="fresh")
    conn = db.connect(str(path))
    flagged = {r[0] for r in conn.execute("SELECT subject_code FROM subject_descriptions WHERE description LIKE '%Indigenous%'")}
    assert flagged == {"31265", "57304"}  # if a third appears, the ethics note must be updated to name it


def test_the_readme_points_at_both_documents():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/SECURITY.md" in readme and "docs/ETHICS.md" in readme


@pytest.mark.parametrize("doc", DOCS)
def test_the_reflection_sections_are_left_for_the_student_to_write(doc):
    text = doc.read_text(encoding="utf-8")
    assert "[YOU WRITE" in text  # these are marked reflections: they must be written by the student, so the placeholder stays until they do
