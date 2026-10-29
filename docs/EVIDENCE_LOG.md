# Evidence log (keep this honest and up to date)

Plan vs actual is part of the A3 reflection. Log as you go.
Goals: 1 ethics, 2 security, 3 dev tools, 4 other

| Date | Goal | What I did | Hours | Commit / PR |
|---|---|---|---|---|
| 2026-10-29 | 3 (dev tools) | Restructured scaffold into a single Flask app, seeded C09119 data, app factory, 17 pytest tests, first PR                | 1 HOUR | PR #1 |
| 2026-10-29 | 3 (dev tools) | Built subject catalogue (search, filters, category headings, colour coding), CI workflow, 58 tests, PR with green CI     | 1 HOUR | PR #2 |
| 2026-10-29 | 2 (security)  | Added users table, salted password hashing, login lockout, input validation, synthetic demo student and 30 tests         | 30 MIN | PR #3 |
| 2026-10-29 | 2 (security)  | Login and logout, sessions, CSRF protection, security headers, record page with ownership check                          | 1 HOUR | PR #4 |
| 2026-10-29 | 2 (security)  | Email login, account creation with password rules, generated student numbers, welcome screen, login-only catalogue       | 1 HOUR | PR #5 |

| 2026-10-29 | 3 (dev tools) | Single eligibility function for every subject (completed, enrolled, can enrol, can't enrol with reasons), 
                                elective limits, greyed-out requirements on the Subjects page, status filter, 39 new tests                              | 30 MIN | PR #6 |

| 2026-10-29 | 2 (security) and 3 (dev tools) | Enrol, withdraw and move between sessions, 24 credit point limit per session, whole-year planning, 
                              CSRF on every change, ownership enforced on the server, atomic room check, 69 new tests                                   | HOURS | PR #7 |



## Things that went wrong or changed
- Dropped the React and TypeScript goal and built a separate Flask project, because the group project belongs to another assessment
- Pushed the wrong folder to a public repo by mistake, then deleted and recreated it
- Changed the prerequisite rule after reviewing the UI: subjects with no rule now show "no prerequisites" instead of "not supplied"
- Switched login from student number to email, and moved the home page to a welcome screen with a login-only catalogue
- Saved the register page template one folder too high, which broke 24 tests with "template not found"; the test suite caught it and I moved the file
- Changed the users table, but my old local database still had the old columns, which caused an internal server error until I deleted it. Tests passed because they build a fresh database each time
- Several test edits were applied to the wrong file or lost a line (missing import, missing variable, duplicated tests); the test run pointed straight at each one
- Decided a prerequisite only counts once completed, so being enrolled in one this session does not unlock the next subject
- Chose to count the per-session limit in credit points (24) rather than subjects, so a 12 cp Honours subject is handled correctly

## AI assistance used (disclose in the report as the subject requires)
- Schema, seed data, tests and catalogue code were drafted with Claude. I reviewed, ran and committed each chunk myself.
- Code, tests and wording were drafted with Claude. I reviewed, ran and committed each chunk myself, and fixed several issues along the way (a missing template, wrongly placed files, edits applied to the wrong test file)
