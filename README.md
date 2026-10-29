# Enrolment Hub

[![CI](https://github.com/AlexChoi2004/enrolment-hub/actions/workflows/ci.yml/badge.svg)](https://github.com/AlexChoi2004/enrolment-hub/actions/workflows/ci.yml)

A small enrolment and degree-planning prototype for one course: Bachelor of Computing Science
(Honours), Enterprise Software Development major. Built with Flask, SQLite and HTMX.

It is an independent educational project, **not an official university system**. All students
are synthetic. Subject codes, names, credit points, categories and prerequisite rules are
supplied reference data (not independently verified); session offerings and general electives
are invented examples.

## What it does so far

- **Subject catalogue:** search by name or code; filter by category, session and prerequisites;
  expandable details; colour-coded categories with the requirement stated under each heading
- **Accounts:** create an account (`firstname.lastname@student.uni.edu.au`, with password rules and
  clear error messages) or log in; salted password hashing, lockout after repeated failures,
  CSRF protection, safe redirects, strict security headers
- **My record:** a synthetic demo student two years into the degree; a student can only view
  their own record (enforced on the server)

Planned: prerequisite and eligibility checks on enrolment, a degree progress planner, a basic
timetable with clash detection, and optional RAG/MCP features.

## Run it

```bash
python -m venv .venv
source .venv/Scripts/activate      # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py                      # http://127.0.0.1:5000
```

Demo login (synthetic student, two years into the degree): `john.doe@student.uni.edu.au` / `Johndoe#1`.
Or click **Create an account** to start as a new Year 1 student with nothing enrolled.

Optional settings (environment variables): `SECRET_KEY` (stable session key; a random one is
generated if unset), `SESSION_COOKIE_SECURE=1` (when serving over HTTPS), `DATABASE_PATH`.

Reset the demo data: `flask --app app reset-demo`

## Test

```bash
python -m pytest -q
```

Tests run automatically on every push and pull request (GitHub Actions).

## Layout

app.py app factory and configuration
accounts/ login, password hashing, lockout
subject_catalogue/ catalogue pages, search and filters
enrolment/ student records
shared/ database helpers, security helpers, base template, CSS
tests/ one folder per feature
docs/ ethics, security and evidence notes


## Docs

- `docs/ETHICS.md`: data governance and responsible AI note (in progress)
- `docs/SECURITY.md`: secure coding case study (in progress)
- `docs/EVIDENCE_LOG.md`: development log