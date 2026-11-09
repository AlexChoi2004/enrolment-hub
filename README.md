# Enrolment Hub

A server-rendered enrolment and degree-planning web app for one degree, the **Bachelor of Computing Science (Honours)**, with
local AI helpers that explain things but never decide them. It uses **synthetic students only** and handbook-style subject data,
and is an independent learning project, not affiliated with or connected to any university system.

All results, marks, class times, due weeks and students are simulated. Subject details and prerequisites follow the public UTS
Handbook, which says its own pages are indicative.

## What it does
- **See where you stand:** a dashboard with progress by requirement, the projected graduation session and your next steps (a React and TypeScript page).
- **Plan by dragging:** a planner board where you drag subjects between sessions (React and TypeScript), and the planner's own rules decide every move and say why when they refuse one.
- **Take it with you:** download your timetable as a calendar file (with the assessment due weeks if you like) for Google, Apple or Outlook calendar.
- **Plan a degree:** choose a major and a sub-major (or general electives), enrol, plan up to ten sessions ahead, and pick classes in a timetable.
- **Enforce the rules:** prerequisites, session offerings, a 24 credit point limit, failed subjects and retakes, with the reason shown whenever something is blocked.
- **Rank by fit:** every major, and every sub-major, ranked for what you have already done, with the same verdicts, credit points lost, extra time and graduation date as each swap page.
- **Check it at the source:** every subject, major, sub-major and the Transdisciplinary stream links to its official UTS Handbook page (opens in a new tab); the majors, sub-majors and language lists were checked against the Handbook's 2027 pages and a test keeps them in step.
- **Compare two programs:** pick two majors (or two sub-majors) to see what they share, what only one has and how their focus differs; each major and sub-major also has a short About tab.
- **Advise on swaps:** changing major, sub-major or electives is never blocked, but you see what carries over, the extra time and a verdict first, and a risky swap needs your own confirmation.
- **Light and dark themes:** follows your device or browser setting, with a toggle that remembers your choice.
- **Test quickly:** a semester simulator (complete, roll back, reset) and four starting points, from a first-year student to one late in their major.
- **Ask questions (AI mode, off by default):** cited answers about rules and subjects, answers about your own plan from read-only tools, and a three-role swap advisor. The code decides and the AI explains; every AI answer is checked by code first.

## Run it
```bash
python -m venv .venv
.venv\Scripts\activate            # Windows (Git Bash: source .venv/Scripts/activate)
pip install -r requirements.txt
python app.py                     # http://127.0.0.1:5000
```
Node is only needed to change the dashboard (the built files are committed, so running the app never needs it):
```bash
cd frontend && npm ci && npm test && npm run build
```
Demo login: `john.doe@student.uni.edu.au` / `Johndoe#1` (the one simulated student; there is no public sign-up).
Delete `enrolment_hub.db` to start from a fresh database.

**AI mode** needs a local model: install [Ollama](https://ollama.com), run `ollama pull qwen3:14b`, then turn **AI mode** on in the top right.
Without a model the app still works and shows the relevant sources instead of a written answer.

| Setting (environment variable) | Default | What it does |
|---|---|---|
| `DEMO_PROFILE` | `fresh` | Starting point of the demo student: `fresh`, `sample`, `late` or `failed` |
| `ALLOW_REGISTRATION` | off | Set to `1` to allow creating accounts (development only) |
| `AI_BACKEND` | `ollama` | `ollama` or `off` |
| `OLLAMA_URL`, `OLLAMA_MODEL` | `http://127.0.0.1:11434`, `qwen3:14b` | Where the model runs and which one |

## Check it
```bash
pip install -r requirements-dev.txt
python -m pytest -q -n auto                    # the whole suite
ruff check --select S --exclude tests .        # security lint, also run in CI
```

## How it is laid out
One Flask app, one SQLite file, one folder per feature. Each feature folder holds its own routes (the web front door), service (the rules),
schema and seed data, and templates (the pages).

```
app.py              starts the app and registers every feature
shared/             database, security (CSRF, headers), base page and styles
features/           one folder per product feature
frontend/           the React and TypeScript dashboard and planner board (built into shared/static/dist)
ai_services/        the AI helpers and what they share
tests/              mirrors features/ and ai_services/
docs/               evidence, security, ethics, architecture and release notes
```

| Feature (`features/`) | What it does |
|---|---|
| `accounts` | Login, profile, sessions and the simulated demo student |
| `subject_catalogue` | Subjects, majors and sub-majors, handbook prerequisites and assessments, filters, short descriptions with Handbook links, and the comparison of two programs |
| `enrolment` | Enrol and withdraw, eligibility rules, results and attempts, the demo starting points |
| `dashboard` | Progress, projected graduation and next steps: the data endpoint and the page that loads the React dashboard |
| `degree_planner` | The planning window, suggested plans, retakes and rescheduling, and the drag-and-drop planner board |
| `timetable` | Class choices, clash detection and a calendar (.ics) download |
| `majors` | Choose or swap a major, with an impact preview, a ranking of every major for your progress, and a side-by-side comparison of two majors |
| `submajors` | Choose or swap a sub-major or general electives, count subjects as electives, rank sub-majors for your progress, and compare two |
| `advisor` | Swap advice: progress, what carries over, extra time, a verdict (rules in code) |
| `transcript` | The Results page |
| `simulator` | Complete a semester, roll it back, reset to a starting point |
| `workload` | Assessment load, due weeks and session workload verdicts |
| `guide` | The Help page |

| AI service (`ai_services/`) | What it does |
|---|---|
| `rag` | Cited answers from the app's own sources, or "Not enough context" |
| `ai_mode` | The tool-using agent that answers questions about the signed-in student |
| `multi_agent` | The swap advisor: an Analyst (code), an Advisor (the AI) and a Checker (code) |
| `mcp_server` | Offers the read-only tools to another AI application over MCP |
| `tools` | The ten read-only tools all of the above share |
| `web` | The AI switch, the question box and the swap advisor pages |

`ai_services/checks.py` holds the checks every AI answer passes, and `ai_services/llm.py` is the model adapter (Ollama, off, or test stand-ins).

## Docs
- `docs/architecture/overview.md` how the pieces fit together (server-rendered pages plus a React island), and how the plan changed
- `docs/SECURITY.md` secure coding case study
- `docs/ETHICS.md` data governance and responsible AI note
- `docs/ACCESSIBILITY.md` what was checked for accessibility, what it found, and what still needs a person
- `docs/MCP.md` using the MCP server from Claude Desktop
- `docs/EVIDENCE_LOG.md` hours, commits and what I actually did
- `docs/release-0/README.md`, `docs/release-1/README.md` and `docs/release-2/README.md` what each release contains
