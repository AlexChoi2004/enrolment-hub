"""The CI and dependency-update configuration, checked as text so it cannot be quietly weakened."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
CODEQL = (ROOT / ".github" / "workflows" / "codeql.yml").read_text(encoding="utf-8")
DEPENDABOT = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")


def test_the_three_ci_jobs_exist_and_the_token_is_read_only():
    for job in ("  test:", "  security:", "  frontend:"):
        assert job in CI
    assert "permissions:\n  contents: read" in CI and "write" not in CI


def test_the_frontend_job_installs_from_the_lock_file_and_runs_every_check():
    job = CI.split("  frontend:", 1)[1]
    for step in ("npm ci", "npm run typecheck", "npm test", "npm run build", "npm audit --audit-level=high", "node --test tests/js/theme.test.mjs"):
        assert step in job, step
    assert "git diff --exit-code -- shared/static/dist" in job  # the committed bundle must match its source
    assert "npm install" not in job.replace("npm ci", "")


def test_the_python_jobs_still_run_the_tests_and_the_security_tools():
    assert "python -m pytest -q" in CI and "ruff check --select S --exclude tests ." in CI and "pip-audit -r requirements.txt" in CI


def test_codeql_scans_both_languages_on_every_change_and_weekly():
    assert "python, javascript-typescript" in CODEQL and "pull_request:" in CODEQL and "cron:" in CODEQL
    assert "security-events: write" in CODEQL and "contents: read" in CODEQL


def test_dependabot_watches_python_npm_and_the_actions_themselves():
    for ecosystem in ("pip", "npm", "github-actions"):
        assert f"package-ecosystem: {ecosystem}" in DEPENDABOT
    assert 'directory: "/frontend"' in DEPENDABOT and "cooldown:" in DEPENDABOT  # a brand-new release waits a week


def test_a_smoke_job_runs_the_real_server_and_the_real_bundle_together():
    job = CI.split("  smoke:", 1)[1]
    assert "python app.py" in job and "node frontend/smoke.mjs http://127.0.0.1:5055" in job and "npm ci" in job
    assert (ROOT / "frontend" / "smoke.mjs").is_file()
    smoke = (ROOT / "frontend" / "smoke.mjs").read_text(encoding="utf-8")
    assert "throw new Error" in smoke and "dashboard never rendered" in smoke  # it fails loudly, never silently
    assert "the board never rendered" in smoke and "the move was not saved" in smoke  # the board is checked too, including a real move


def test_the_smoke_job_also_runs_the_accessibility_audit_on_every_page():
    job = CI.split("  smoke:", 1)[1]
    assert "node frontend/a11y.mjs http://127.0.0.1:5055" in job and "ALLOW_REGISTRATION=1" in job  # registration on, so the sign-up page is audited
    audit = (ROOT / "frontend" / "a11y.mjs").read_text(encoding="utf-8")
    assert "process.exit(total === 0 ? 0 : 1)" in audit and "wcag22aa" in audit  # any violation fails the build
    assert '"color-contrast": { enabled: false }' in audit  # the one rule jsdom cannot run, covered by the token tests
    for page in ("Dashboard (React)", "Planner board (React)", "Simulator: roll back", "Choose a sub-major", "Compare two majors", "Compare two sub-majors", "Fit for my progress: majors", "Major: About tab"):
        assert page in audit


def test_the_test_job_installs_the_independent_calendar_parser_so_that_check_runs_in_ci():
    job = CI.split("  test:", 1)[1].split("  security:", 1)[0]
    assert "icalendar" in job and "recurring-ical-events" in job
    assert "icalendar" in (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
