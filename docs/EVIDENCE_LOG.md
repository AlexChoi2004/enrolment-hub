# Evidence log (keep this honest and up to date)

Plan vs actual is part of the A3 reflection. Log as you go.
Goals: 1 ethics, 2 security, 3 dev tools, 4 other

| Date | Goal | What I did | Hours | Commit / PR |
|---|---|---|---|---|
| 2026-10-29 | 3 (dev tools) | Restructured scaffold into a single Flask app, seeded C09119 data, app factory, 17 pytest tests, first PR                | 1 HOUR | PR #1  |
| 2026-10-29 | 3 (dev tools) | Built subject catalogue (search, filters, category headings, colour coding), CI workflow, 58 tests, PR with green CI     | 1 HOUR | PR #2  |
| 2026-10-29 | 2 (security)  | Added users table, salted password hashing, login lockout, input validation, synthetic demo student and 30 tests         | 30 MIN | PR #3  |
| 2026-10-29 | 2 (security)  | Login and logout, sessions, CSRF protection, security headers, record page with ownership check                          | 1 HOUR | PR #4  |
| 2026-10-29 | 2 (security)  | Email login, account creation with password rules, generated student numbers, welcome screen, login-only catalogue       | 1 HOUR | PR #5  |
| 2026-10-29 | 3 (dev tools) | Single eligibility function for every subject (completed, enrolled, can enrol, can't enrol with reasons),                | 30 MIN | PR #6  |
             |               | elective limits, greyed-out requirements on the Subjects page, status filter, 39 new tests                               |        |        |
| 2026-10-29 | 2 (security) and 3 (dev tools) | Enrol, withdraw and move between sessions, 24 credit point limit per session, whole-year planning,      | 1 HOUR | PR #7  |
             |                                | CSRF on every change, ownership enforced on the server, atomic room check, 69 new tests                 |        |        |
| 2026-10-30 | 2 (security) and 3 (dev tools) | Added Ruff security rules and a dependency audit to CI; ran detect-secrets locally                      | 10 MIN | PR #8  |
| 2026-10-30 | 3 (dev tools) | Moved navigation (Subjects, Record on the left; Profile on the right), added a profile page with details, progress,      | 15 MIN | PR #9  |
             |               | what the app stores, and the log out button, 15 new tests                                                                |        |        |
| 2026-10-30 | 3 (dev tools) | Built the degree planner: plan subjects into future sessions (add, move, remove, clear), placement rules (offering,      | 1 HOUR | PR #10 |
                               24 cp, prerequisites in an earlier session, elective limits), suggested plan, outstanding requirements, stale-plan       |        |        |
                               warnings and the nav link; kept finished elective sections visible with a completion note; kept scroll position and      |        |        |
                               open cards after actions; floating messages; 465 tests                                                                   |        |        |
| 2026-10-31 | 3 (dev tools) | Built the timetable: invented weekly classes (varied lecture, tutorial and workshop patterns with 5 to 10 time options   | 2 HOUR | PR #11 |
                               each), weekly view for each session with a colour per subject, choose, change and drop classes, clashes allowed with
                               a warning and shown in red, and the nav link; 83 new tests



## Things that went wrong or changed

### Before PR #1: repo setup
- Dropped the React and TypeScript goal and built a separate Flask project, because the group project belongs to another assessment
- Pushed the wrong folder to a public repo by mistake, then deleted and recreated it

### PR #2: Subject catalogue
- Changed the prerequisite rule after reviewing the UI: subjects with no rule now show "no prerequisites" instead of "not supplied"

### PR #5: Email login, registration and welcome screen
- Switched login from student number to email, and moved the home page to a welcome screen with a login-only catalogue
- Saved the register page template one folder too high, which broke 24 tests with "template not found"; the test suite caught it and I moved the file
- Changed the users table, but my old local database still had the old columns, which caused an internal server error until I deleted it. Tests passed because they build 
  a fresh database each time
- Several test edits were applied to the wrong file or lost a line (missing import, missing variable, duplicated tests); the test run pointed straight at each one

### PR #6: Subject status
- Decided a prerequisite only counts once completed, so being enrolled in one this session does not unlock the next subject

### PR #7: Enrol, withdraw and move
- Chose to count the per-session limit in credit points (24) rather than subjects, so a 12 cp Honours subject is handled correctly

### PR #8: Security scans in CI
- Ruff flagged the public demo password as a hardcoded secret; I suppressed that one rule with a stated reason rather than hiding it
- Postponed writing `SECURITY.md` and `ETHICS.md` until the AI features exist, so the ethics note describes what was actually built

### PR #9: Profile page and navigation
- Moved Log out from the header to the profile page, as I wanted a cleaner header with the account on the right
- Left the Degree planner and Timetable links out of the nav until those pages exist, so there are no dead links
- Decided the email is shown on the profile page only, and kept it out of the session user used by every other page
- Saved the profile page template one folder too high, which broke 10 tests with "template not found"; the test run named the missing file and I moved it

### PR #10: Degree planner
- Decided a plan is separate from enrolling, and a subject leaves the plan automatically once I enrol in it
- Let the planner treat a prerequisite as met when it is planned or enrolled in an earlier session, which is looser than enrolling (needs completed); this is 
  what makes planning a whole chain ahead possible
- Decided planned subjects count towards elective limits, and kept the same 24 credit point cap per session
- Chose a ten-session planning window (five years) so a suggested plan has room to spread out; a new student's plan fits in eight
- Found that a suggested plan can place Honours Project B before Honours Project A, because the supplied prerequisite data only links A to 
  Technology Research Preparation; I did not invent a rule and noted it as a data limitation
- Made suggestions use exactly the same checks as manual changes, and added a test that every suggested placement passes them
- Saved the planner page as `index,html` with a comma instead of `index.html`, so Flask could not find it; I only spotted it when I looked closely at the file 
  name and renamed it
- Changed finished elective sections to stay on screen with a "you've already completed or chosen all" note instead of disappearing, so the page does not 
  seem to lose information
- Reloading the page after every action sent me back to the top, so I added a small script that remembers the scroll position and which cards were open; 
- Moved confirmation and error messages into floating messages in the corner, because once I stay where I was on the page, messages at the top would be out of sight

### PR #11: Timetable
- Changed the invented timetable so each subject follows one of four patterns (lecture and tutorial; with a workshop; with two tutorials; lecture and workshop) and 
  every tutorial and workshop has 5 to 10 time options, so it is easier to find a time that does not clash
- Changed clash handling from refusing a clashing class to allowing it with a warning and drawing both classes in red, because I wanted to see a clash when I choose 
  one; I updated the tests to match
- Changed the weekly view from a table to day columns, so two overlapping classes sit side by side instead of the second one being left out
- Changed lecture lengths and placement so lectures avoid each other, which cut lecture clashes from 15 pairs to 2 in Autumn, and gave each subject its own colour 
  (shared by its lecture, tutorials and workshop)
- Fixed a bug where chosen tutorials lost their subject, because the query returned two columns both called `subject_code`; the tests showed it straight away
- Changed two queries that built their `IN (...)` lists with string formatting to filter in Python, so the security lint passes without me suppressing anything
- Marked the two seeded random generator lines with a stated reason after the security lint flagged them; they only produce repeatable invented data and are not \
  used for security
- Changed withdrawing and moving a subject to remove its class choices, so the timetable never shows a class for something I am no longer enrolled in
- Used CSS classes for positions and colours instead of inline styles, because my security policy blocks inline styles


## AI assistance used (disclose in the report as the subject requires)
- Schema, seed data, tests and catalogue code were drafted with Claude. I reviewed, ran and committed each chunk myself.
- Code, tests and wording were drafted with Claude. I reviewed, ran and committed each chunk myself, and fixed several issues along the way (a missing template,
  wrongly placed files, edits applied to the wrong test file)
