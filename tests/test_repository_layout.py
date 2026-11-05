"""Keeps the repository tidy and the README honest: no placeholders, no old folders, every feature and service documented."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache", "node_modules"}
OLD_TOP_LEVEL = ["accounts", "subject_catalogue", "enrolment", "degree_planner", "timetable", "majors", "submajors", "transcript",
                 "simulator", "workload", "advisor", "guide", "rag", "tools", "mcp_server", "data", "scripts"]


def files(pattern):
    return [p for p in ROOT.rglob(pattern) if not (set(p.relative_to(ROOT).parts) & SKIP)]


def packages(folder):
    return sorted(p.name for p in (ROOT / folder).iterdir() if p.is_dir() and p.name not in SKIP and not p.name.startswith("."))


README = (ROOT / "README.md").read_text(encoding="utf-8")


def test_there_are_no_placeholder_files():
    assert files(".gitkeep") == []


def test_there_are_no_empty_folders():
    empty = [p for p in ROOT.rglob("*") if p.is_dir() and not (set(p.relative_to(ROOT).parts) & SKIP) and not any(p.iterdir())]
    assert empty == []


def test_the_old_top_level_folders_are_gone():
    assert [name for name in OLD_TOP_LEVEL if (ROOT / name).is_dir()] == []


def test_every_python_folder_is_a_package():
    missing = sorted({str(p.parent.relative_to(ROOT)) for p in files("*.py")
                      if p.parent != ROOT and p.parent.parts[0] in ("features", "ai_services", "shared") and not (p.parent / "__init__.py").exists()})
    assert missing == []


def test_every_feature_is_in_the_readme():
    names = [n for n in packages("features")]
    assert names and [n for n in names if f"`{n}`" not in README] == []


def test_every_ai_service_is_in_the_readme():
    names = packages("ai_services")
    assert names and [n for n in names if f"`{n}`" not in README] == []


def test_the_readme_does_not_list_folders_that_do_not_exist():
    table = README.split("| Feature (`features/`)", 1)[1].split("| AI service", 1)[0]
    listed = re.findall(r"^\| `(\w+)` \|", table, re.M)
    assert sorted(listed) == packages("features")
    ai_table = README.split("| AI service (`ai_services/`)", 1)[1].split("`ai_services/checks.py`", 1)[0]
    assert sorted(re.findall(r"^\| `(\w+)` \|", ai_table, re.M)) == packages("ai_services")


def test_every_doc_the_readme_points_to_exists():
    for path in re.findall(r"`(docs/[\w./-]+\.md)`", README):
        assert (ROOT / path).is_file(), path


def test_the_tests_mirror_the_layout():
    assert packages("tests/features") == sorted(n for n in packages("features"))
    assert set(packages("tests/ai_services")) <= set(packages("ai_services"))


def test_the_readme_describes_what_is_actually_built():
    assert "microservice" not in README.lower() and "one SQLite file" in README and "never opens another feature" not in README


def test_the_release_notes_are_filled_in():
    for n in (0, 1, 2):
        text = (ROOT / "docs" / f"release-{n}" / "README.md").read_text(encoding="utf-8")
        assert "Scope:** " in text and "Known issues:** " in text and text.count("- **") == 4
