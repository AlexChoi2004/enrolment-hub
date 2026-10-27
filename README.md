# Enrolment Hub

A small microservice-style enrolment application for a single degree
(Bachelor of Computing Science (Honours)). It uses **synthetic students only**
and handbook-style subject data. It is an independent learning project and is
not affiliated with or connected to any university system.

Built in releases: R0 (core app) -> R1 (RAG, MCP, AI mode) -> R2 (multi-agent).

## Features (one folder each)

| Folder | What it does |
|---|---|
| `accounts/` | Register, log in, hashed passwords, signed tokens |
| `subject-catalogue/` | Browse and search subjects, prerequisites, credit points |
| `enrolment/` | Enrol and drop, prerequisite / capacity / clash checks |
| `degree-planner/` | Plan sessions and track progress against course rules |

Each feature has `frontend/` (Flask + HTMX), `backend/` (API),
`database/` (SQLite behind its own API) and `tests/`.
A backend never opens another feature's SQLite file; it calls that feature's
database API instead.

## Docs

- `docs/ETHICS.md` data governance and responsible AI note
- `docs/SECURITY.md` secure coding case study
- `docs/EVIDENCE_LOG.md` hours, commits and what I actually did
- `docs/portfolio/` screenshots and write-ups for the report

## Run (filled in as releases land)

See each release folder in `docs/`.
