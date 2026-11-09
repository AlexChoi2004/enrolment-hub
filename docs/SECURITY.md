# Secure coding case study

**Project:** Enrolment Hub, a Flask, SQLite and HTMX app with two React and TypeScript pages, for one degree (Bachelor of Computing Science (Honours), C09119).
**Scope:** the application code in this repository, its build pipeline and its optional AI features. It is a prototype that holds **synthetic students only**; nothing here has had a penetration test or an independent review (see "Known gaps").

Every control below names the file that implements it and the tests that check it. `tests/test_docs_claims.py` fails if a file or test named in this document does not exist, so the table cannot quietly go out of date.

## 1. What is protected, and from whom

| Asset | Why it matters | Realistic threats |
|---|---|---|
| A student's record (results, plan, timetable, enrolments) | In a real deployment it is personal information that affects progression | another student reading or changing it; a stolen or reused session |
| Accounts and sessions | They gate everything else | guessing passwords, credential stuffing, session theft or fixation, forged requests from another site |
| The AI features | They turn free text into database lookups | prompt injection, answers that invent facts, a model asked about another student (the model runs on the same computer by default, so questions do not leave the machine) |
| The catalogue (Handbook-derived structure) | Wrong rules mislead degree decisions | a link or value that points somewhere other than the Handbook |
| The build and its dependencies | Code you did not write runs in your app | a malicious or vulnerable package version |

The design assumption is the one that matters most for a student system: **the signed-in student is the only person who may see or change their own record, and every request is untrusted until proved otherwise.**

## 2. Controls, where they live, and what tests them

| Risk | Control | Where | Tests |
|---|---|---|---|
| Stolen password database | Passwords stored only as salted scrypt hashes (Werkzeug); the hash is never returned to a page | `features/accounts/service.py` | `tests/features/accounts/test_accounts_service.py::test_demo_password_is_stored_as_a_salted_hash_not_plaintext`, `tests/features/accounts/test_accounts_service.py::test_same_password_hashes_differently_each_time`, `tests/features/accounts/test_register_routes.py::test_new_accounts_store_a_hash_not_the_password`, `tests/features/accounts/test_accounts_service.py::test_get_user_returns_no_password_hash` |
| Weak passwords | At least 8 characters with an upper-case letter, a lower-case letter, a number and a special character, and a maximum length | `features/accounts/service.py` (`password_problems`) | `tests/features/accounts/test_accounts_service.py::test_create_user_stores_a_hash_and_generates_a_student_number` |
| Password guessing | Five wrong passwords lock the account for five minutes, even if the next password is right | `features/accounts/service.py` (`MAX_FAILED_LOGINS`, `LOCKOUT_SECONDS`) | `tests/features/accounts/test_accounts_service.py::test_account_locks_after_repeated_failures_even_with_correct_password`, `tests/features/accounts/test_accounts_service.py::test_lockout_expires`, `tests/features/accounts/test_accounts_routes.py::test_account_locks_after_five_wrong_passwords_even_for_the_right_one` |
| Learning which emails have accounts | One generic failure message; for an unknown email a dummy hash is still compared; logs carry a one-way tag, not the email | `features/accounts/service.py` | `tests/features/accounts/test_accounts_routes.py::test_wrong_password_is_rejected_with_a_generic_message` |
| Session reuse and fixation | The session is cleared and replaced on login and cleared on logout; cookies are `HttpOnly`, `SameSite=Lax`, expire after two hours, and are `Secure` when `SESSION_COOKIE_SECURE=1` | `features/accounts/routes.py`, `app.py` | `tests/features/accounts/test_accounts_routes.py::test_logout_clears_the_session`, `tests/test_docs_claims.py::test_the_session_cookie_settings_match_this_document` |
| Forged requests from another site (CSRF) | Every POST needs this session's token, sent as a form field or an `X-CSRF-Token` header, compared in constant time | `shared/security.py` (`csrf_valid`, `require_csrf`) | `tests/test_security.py::test_post_without_a_token_is_rejected`, `tests/test_security.py::test_post_with_a_wrong_token_is_rejected`, `tests/test_security.py::test_non_ascii_token_is_rejected_not_a_server_error`, `tests/features/accounts/test_register_routes.py::test_registration_with_a_forged_csrf_token_is_rejected`, `tests/ai_services/web/test_ai_mode_pages.py::test_the_switch_needs_a_login_and_a_csrf_token` |
| Open redirects after login | `next` is accepted only if it is a same-site path; `//evil.example` and absolute URLs are refused | `shared/security.py` (`safe_next`) | `tests/test_security.py::test_safe_next_rejects_everything_else`, `tests/test_security.py::test_safe_next_accepts_same_site_paths`, `tests/ai_services/web/test_ai_mode_pages.py::test_the_switch_returns_to_the_same_page_and_never_to_another_site` |
| Script injection and framing | `Content-Security-Policy` allows only this site's own scripts and styles, with no inline script, `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: same-origin` | `shared/security.py` (`apply_security_headers`) | `tests/test_security.py::test_security_headers_are_applied`, `tests/shared/test_theme.py::test_the_script_is_served_and_the_policy_still_blocks_inline_scripts` |
| One student reading another's data | Every page and API is behind `login_required`, and every query is scoped to the signed-in student's id, never an id from the request | `shared/security.py` (`login_required`) and each feature's service | `tests/features/majors/test_fit.py::test_one_student_never_sees_anothers_numbers`, `tests/features/timetable/test_export.py::test_a_new_student_never_gets_the_demo_students_classes`, `tests/ai_services/tools/test_tools.py::test_each_student_gets_only_their_own_data` |
| Personal pages kept by a browser or proxy | Personal JSON, pages and the calendar file are sent with `Cache-Control: no-store` | each feature's routes | `tests/features/dashboard/test_dashboard.py::test_the_endpoint_returns_the_students_own_data_and_is_never_cached`, `tests/features/degree_planner/test_board.py::test_the_board_data_is_the_students_own_and_never_cached`, `tests/features/timetable/test_export.py::test_the_answer_is_a_downloadable_calendar_that_is_never_cached` |
| SQL injection | Every query is parameterised; table and column names are never built from input; `ruff` security rules (bandit) run in CI | all `features/*/service.py` files, `.github/workflows/ci.yml` | `tests/features/subject_catalogue/test_catalogue_service.py::test_sql_injection_text_is_treated_as_plain_text` |
| Malformed or hostile input | Codes, sessions and bodies are checked against allow-lists or strict shapes and refused with a 400 before any work is done; bad values are never echoed back | route and service layers | `tests/features/majors/test_compare_pages.py::test_a_malformed_code_is_a_400_and_never_echoed`, `tests/features/timetable/test_timetable_routes.py::test_malformed_input_returns_400`, `tests/features/degree_planner/test_board.py::test_a_malformed_move_is_refused_before_anything_runs`, `tests/features/degree_planner/test_board.py::test_the_body_must_be_json` |
| Cross-site scripting through output | Templates escape by default; the React pages render text as text; model output and the student's question are escaped | templates, `frontend/src` | `tests/ai_services/web/test_ai_mode_pages.py::test_the_models_text_is_escaped`, `tests/ai_services/web/test_ai_mode_pages.py::test_the_question_is_escaped_on_the_full_page`, `tests/ai_services/web/test_ai_mode_pages.py::test_the_agents_text_is_escaped` |
| Injecting lines into the downloaded calendar | Text in the `.ics` file is escaped so a subject name cannot add a line | `features/timetable/ical.py` | `tests/features/timetable/test_ical.py::test_text_cannot_add_a_line_to_the_file` |
| Anyone creating accounts | Public sign-up is off unless `ALLOW_REGISTRATION=1`; when on, it closes at an account limit | `app.py`, `features/accounts/routes.py` | `tests/features/guide/test_real_defaults_and_guide.py::test_registration_can_be_switched_back_on_for_development`, `tests/features/accounts/test_register_routes.py::test_registration_closes_when_the_account_limit_is_reached` |
| Demo controls used by a real student | Reset, finish and roll-back are for the demo account only (403 for anyone else) | `features/simulator/routes.py` (`_demo_only`) | `tests/features/simulator/test_simulator_pages.py::test_only_the_demo_student_can_use_the_simulator`, `tests/features/simulator/test_semester_controls.py::test_only_the_demo_student_can_roll_back` |
| A "Handbook" link that goes elsewhere | A database check allows a stored Handbook link only on `https://coursehandbook.uts.edu.au/` | `features/subject_catalogue/schema.sql` | `tests/features/subject_catalogue/test_handbook_links.py::test_a_link_can_only_point_at_the_handbook` |
| AI used unasked | AI mode is off by default and the box is hidden until a student switches it on | `ai_services/ai_mode`, `ai_services/web` | `tests/ai_services/web/test_ai_mode_pages.py::test_ai_mode_is_off_by_default_and_the_box_is_hidden` |
| A model reading or changing another student's data | The student is fixed by the server, not named by the model; the tools only look things up | `ai_services/tools` | `tests/ai_services/ai_mode/test_agent.py::test_a_model_cannot_name_another_student`, `tests/ai_services/tools/test_tools.py::test_a_model_cannot_ask_about_another_student`, `tests/ai_services/web/test_ai_mode_pages.py::test_the_tools_only_ever_see_the_signed_in_student`, `tests/ai_services/ai_mode/test_agent.py::test_running_the_agent_never_changes_any_data` |
| Prompt injection and invented answers | Retrieval only from the app's own sources; every AI answer passes shared checks (links, numbers, leaked instructions, claims of an action, length) or is replaced by a plain answer | `ai_services/checks.py`, `ai_services/rag` | `tests/ai_services/rag/test_answer_and_model.py::test_a_long_injection_in_the_question_finds_no_sources_and_never_reaches_the_model`, `tests/ai_services/test_checks.py::test_every_path_rejects_a_leaked_prompt`, `tests/ai_services/test_checks.py::test_claims_of_an_action_are_found`, `tests/ai_services/test_checks.py::test_numbers_in_the_answer_must_come_from_the_allowed_text` |
| The MCP server (for Claude Desktop) | Ten read-only tools with closed schemas, a read-only snapshot of the data, never a write path | `ai_services/mcp_server/server.py` | `tests/ai_services/mcp_server/test_mcp_server.py::test_the_ten_tools_are_listed_as_read_only_with_closed_schemas`, `tests/ai_services/mcp_server/test_mcp_server.py::test_the_file_is_opened_read_only`, `tests/ai_services/mcp_server/test_mcp_server.py::test_even_a_deliberate_write_to_the_snapshot_never_reaches_the_file`, `tests/ai_services/mcp_server/test_mcp_server.py::test_malformed_tool_calls_are_invalid_params` |
| Malicious or vulnerable dependencies | Exact pinned versions and a lock file; new versions are chosen only if they are at least two weeks old (a working rule, not enforced by tooling); `pip-audit` and `npm audit` in CI; Dependabot for pip, npm and Actions; CodeQL on every pull request | `frontend/package.json`, `.github/workflows/ci.yml`, `.github/workflows/codeql.yml`, `.github/dependabot.yml` | `tests/features/dashboard/test_contract.py::test_the_frontend_pins_exact_versions_and_a_lock_file`, `tests/test_ci_config.py::test_the_frontend_job_installs_from_the_lock_file_and_runs_every_check` |
| Secrets in the repository | `SECRET_KEY` comes from the environment (a random key per start if unset); `.env` and `*.db` are ignored by Git; `.env.example` holds only names | `app.py`, `.gitignore`, `.env.example` | `tests/test_docs_claims.py::test_the_secret_key_comes_from_the_environment_and_secrets_are_ignored` |

## 3. What I found by testing, not by reading

- **A link value that would send a student to another site.** While writing the dashboard's typed contract, a test showed that a "next step" link field would accept `//evil.example`, which a browser treats as another site. The contract now accepts only same-site paths, and the same rule is checked on the Python and the TypeScript side from shared fixtures (`tests/features/dashboard/test_contract.py::test_the_contract_only_allows_links_that_stay_on_this_site`).
- **Tests that could not fail.** Some early style tests passed vacuously because the test runner blanks CSS. They were rewritten to check the real stylesheet. This is a security-adjacent lesson: a green test is only evidence if it can go red.
- **A process slip, not a code one.** Work was pushed straight to `main` twice before every change went through a branch and a pull request. The fix was a procedure (a new branch for every change, a script that refuses to apply work on `main`) and, once confirmed in the repository settings, required checks on `main`.

## 4. Known gaps (read this before trusting the table)

- **No independent review.** Nothing here was penetration tested or reviewed by a security professional. CodeQL, `ruff` and the audits are automated and find known patterns only.
- **Repository protections are settings, not code.** Branch protection and required checks cannot be proved by a test. Evidence for them is a screenshot of the repository settings (add one to the evidence log).
- **HTTPS is not enforced by the app.** The `Secure` cookie flag is opt-in (`SESSION_COOKIE_SECURE=1`), no `Strict-Transport-Security` header is sent, and the Flask development server is not a production server. A real deployment needs TLS and a production WSGI server in front.
- **No multi-factor authentication, and lockout can be abused.** An attacker who knows an email can lock that account for five minutes. That is a deliberate trade-off against password guessing, not a solved problem. There is no per-address throttle beyond the account lockout.
- **Timing is not tested.** The dummy hash for unknown emails is there to even out response time, but no test measures it.
- **The database is a plain SQLite file** with no encryption at rest.
- **The AI checks reduce wrong or manipulated answers; they do not remove them.** The verdicts themselves ("Good to switch", the workload rating) are computed by tested code, and the model only explains them, but the wording of an explanation can still mislead. There is no automated evaluation set that measures this (a future goal).
- **The Handbook-derived data is as good as what was supplied.** Structures were checked against the Handbook's 2027 pages on 8 November 2026 (`features/subject_catalogue/handbook_2027.py`); other fields, such as most subjects' sessions, are illustrative and labelled so.

## 5. Mapping to common checklists

| OWASP Top 10 (2021) | Where this project addresses it |
|---|---|
| A01 Broken access control | login required everywhere; every query scoped to the signed-in student; demo controls limited to the demo account |
| A02 Cryptographic failures | salted scrypt password hashes; no plaintext or reversible secrets stored; `Secure` cookie option (TLS itself is a deployment task) |
| A03 Injection | parameterised SQL; escaped output; `.ics` escaping; strict input shapes |
| A04 Insecure design | the signed-in student is fixed by the server, including for AI tools; AI tools are read-only; deterministic code decides, the model explains |
| A05 Security misconfiguration | restrictive CSP and headers; registration off by default; secrets from the environment |
| A06 Vulnerable and outdated components | pinned and locked versions, a two-week-old rule when choosing versions, audits, Dependabot, CodeQL |
| A07 Identification and authentication failures | password rules, lockout, generic failures, new session on login |
| A08 Software and data integrity failures | lock file installs (`npm ci`), committed bundle checked against a rebuild in CI, a database check on stored links |
| A09 Logging and monitoring failures | login failures are logged against a one-way tag; **no alerting or central log review exists** (gap) |
| A10 Server-side request forgery | nothing a student types is ever fetched; the only outbound request is to the local AI model's address, set in the server's settings and checked to be http or https (`ai_services/llm.py`) |

## 6. How to re-check this yourself

```bash
python -m pytest -q -n auto                       # all tests, including the checks behind this table
python -m pytest -q tests/test_docs_claims.py     # that every file and test named here exists
ruff check --select S --exclude tests .           # security lint on the application code
pip-audit -r requirements.txt                     # known vulnerabilities in Python dependencies
cd frontend && npm audit                          # and in the frontend's
```

## 7. What I learned (my own words)

*[YOU WRITE: three to five sentences. Prompts: which control was harder than you expected and why; one thing a test showed you that you had not seen by reading; what you would do differently on the next project. Keep it specific to something that happened in this repository.]*
