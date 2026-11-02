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
                             | 24 cp, prerequisites in an earlier session, elective limits), suggested plan, outstanding requirements, stale-plan       |        |        |
                             | warnings and the nav link; kept finished elective sections visible with a completion note; kept scroll position and      |        |        |
                             | open cards after actions; floating messages; 465 tests                                                                   |        |        |
| 2026-10-31 | 3 (dev tools) | Built the timetable: invented weekly classes (varied lecture, tutorial and workshop patterns with 5 to 10 time options   | 2 HOUR | PR #11 |
                             | each), weekly view for each session with a colour per subject, choose, change and drop classes, clashes allowed with     |        |        |
                             | a warning and shown in red, and the nav link; 83 new tests                                                               |        |        |
| 2026-11-01 | 3 (dev tools) | Added the seven other majors from my supplied data (60 more subjects) with their core and option structure, a major      | 2 HOUR | PR #12 |
                             | chooser (list, preview, confirm, swap), and a per-student degree that the Subjects page, enrolment, record, profile,     |        |        |
                             | planner and timetable all follow; the added subjects' prerequisites (alternatives, a corequisite and a credit-point      |        |        |
                             | condition) enforced like the originals; 695 tests                                                                        |        |        |
| 2026-11-02 | 3 (dev tools) | Added short descriptions and assessment information for every subject, read from the UTS Handbook (85 subjects) with     | 1 HOUR | PR #13 |
                             | 2 historical, 6 unconfirmed and 12 sample electives; each assessment structure carries a source, year and verification   |        |        |
                             | label; unconfirmed subjects say there is no breakdown yet; a single function decides what the AI features may use, and   |        |        |
                             | says "not enough context" otherwise; 56 new tests                                                                        |        |        |
| 2026-11-02 | 3 (dev tools) | Compared my prerequisites with the UTS Handbook for every subject I could read, then matched them: 34 rules added and    | 1 HOUR | PR #14 |
                             |7 corrected, degree-wide credit-point conditions, corequisites, the handbook's wording kept as notes where the app cannot |        |        |
                             |enforce it, five subject names corrected, and the demo student's history fixed; 24 new tests                              |        |        |
| 2026-11-02 | 3 (dev tools) | Fixed the prerequisite filter dropdown, which sent values the server no longer accepted, and hid the Apply button unless | 10 MIN | PR #15 |
                             | JavaScript is off                                                                                                        |        |        |
| 2026-11-02 | 3 (dev tools) | Added eight 24 cp sub-majors with core and option groups, a language sub-major with one chosen program of 8 cp subjects, | 2 HOUR | PR #16 |
                             | and a stream; 76 new subjects stored once; the 24 cp block is now a choice between a sub-major and general electives; a  |        |        |
                             | chooser with an impact preview; major, sub-major and electives swaps are never blocked and can withdraw in-progress      |        |        |
                             | subjects that stop counting; the planner and enrolment handle choose-groups in credit points and flag overlaps with the  |        |        |
                             | major; filters apply only on Apply with a Reset button; about 150 new tests c                                            |        |        |


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

### PR #12: Majors
- Changed the degree data so each student has their own view of the degree: a subject now counts as major core, a major elective or not part of their degree depending 
  on the major they chose, instead of having one fixed category
- Added the seven other majors from my supplied data (eight with Enterprise Software Development), checked that each totals exactly 48 credit points, and stored shared 
  subjects such as Capstone once with a membership row per major
- Changed new accounts to start with no major, and to choose one from a short list, then a preview of one major's core and options, then a confirm button, so the Subjects 
  page does not get cluttered with every major
- Changed the prerequisites from my research notes into real rules, so the added subjects behave like the original ones: "has prerequisites" with met and not-met marks,
  or "no prerequisites", and enforced on enrolment and in the planner
- Changed the prerequisite model so a subject can have alternatives (A or B) and a corequisite that can be taken at the same time, and added a separate credit-point condition 
  so reaching a threshold can never stand in for a required subject
- Fixed Business Information Systems, whose core subject Data Visualisation needed a subject that is not in that major, by adding the alternative Introduction to Information 
  Systems that my notes suggested; without it a student could never finish that major
- Decided the external prerequisite 41004 (not a subject in my data) and the leads for three original subjects stay as "not enforced" notes, because enforcing them would make 
  a subject impossible to take or change the supplied rules
- Decided that the demo student cannot swap major because their completed subjects only count in their current major, while a new account can swap until it has enrolled in
  subjects only the old major has
- Changed the planner so it plans the student's own major, removes planned subjects that are not in a new major when swapping, and treats a student without a major as having
  48 credit points still to plan
- Changed the timetable generator to place the original subjects first, so their class times do not move when new subjects are added
- Changed the Unlocks list to show only subjects the student could actually take
- Fixed about twenty-five existing tests that assumed every new account has the Enterprise Software Development major, or that the added prerequisites were not enforced
- Fixed the users table missing the new `major_code` column, which made hundreds of tests error until I added it to the schema file
- Fixed two planner test files that used a session constant that only exists in a third file
- Fixed the majors templates folder being named `major` instead of `majors`, so Flask could not find the pages

### PR #13: Subject descriptions and assessments
- Changed the catalogue so descriptions and assessment records are stored separately, and a subject can have several assessment structures over time, so a real outline 
  can replace older information without deleting it
- Decided that handbook information is labelled "indicative", because the handbook says so itself, and that information from an older year is labelled historical with 
  a warning
- Decided not to invent anything for real subjects without a confirmed breakdown: they store no tasks and tell the student they will find out when they enrol, and the 
  older student-reported tasks for one subject are kept as an internal note only
- Changed the AI helper so it only receives confirmed or clearly labelled information and says "not enough context" otherwise, so the planner AI cannot talk 
  about assessments I have not verified
- Fixed my plan to read every subject from the handbook after finding that six of the pages block automated access; I did not work around that and used the descriptions 
  and historical information I was given instead
- Decided to keep the explanations of each task general to its type instead of copying handbook text

### PR #14: Prerequisites matched to the handbook
- Changed my prerequisites from the supplied rules and research leads to the UTS Handbook's requisites, after finding that my own leads were wrong for several subjects 
  (for example Fundamentals of Interaction Design has no prerequisite at all)
- Decided to enforce only the alternatives that exist in my app and keep the full handbook wording as a visible note, because many handbook requisites accept subjects 
  from other faculties that I do not have
- Decided not to enforce the handbook rule for Data Visualisation, because Business Information Systems makes it core but the subject it requires is not in that major,
  and showed it as a note instead
- Changed credit-point conditions so they can apply to the whole degree as well as to one major, and made the planner count credit planned in earlier sessions
- Fixed the demo student's history after the new rules showed that Database Fundamentals was taken before Programming 1; I swapped two subjects between sessions so 
  his totals did not change
- Fixed five subject names that did not match the handbook, including Real Analysis, which I had called Mathematics 3
- Fixed about 40 existing tests that assumed the old rules, and added a test that every major still produces a full plan
- Decided to leave six subjects on their old rules because their handbook pages block automated access

### PR #15: Filter dropdown fix
- Fixed the prerequisite filter dropdown, which still sent the old values (`supplied` and `not_supplied`) after I changed the filter to `required` and `none`, 
  so both options showed "Unknown prerequisite filter"
- Fixed it by editing the page, because my tests asked for the filter URLs directly and so never clicked the dropdown, which is how the stale options got past them
- Changed the Apply button to show only when JavaScript is off, because the list already updated as soon as any filter changed and the button did nothing useful


### PR #16: Sub-majors, electives choice and swaps
- Changed the degree so the 24 cp block is core 96 + honours 24 + major 48 + either a sub-major or general electives, and made each choice switch the other off
- Changed the planner and enrolment so they count requirements in credit points instead of assuming 6 cp electives, which was needed for the 8 cp language subjects 
  and for groups like "select 18 cp from six subjects"
- Added the eight sub-majors from my supplied handbook text as groups of core subjects and options, with a language sub-major where I pick exactly one language, 
  and a stream stored as its own record with its subjects left empty because they were not supplied
- Decided that a subject in both the major and the sub-major counts once, in the major, and is flagged, because the course rules for overlaps need verifying and I 
  did not want to double-count
- Decided swapping a major, sub-major or the electives choice is never blocked; the app shows what carries over and what stops counting first, keeps everything on 
  the record, and counts only what counts towards the degree in the totals
- Changed the swap so in-progress subjects that stop counting can be withdrawn as part of it (ticked by default), because leaving them enrolled kept them in my session 
  load even though they no longer counted; completed subjects are never touched
- Decided to leave language prerequisites, sequencing and the placement assessment unverified and not enforced, and to say so on the page
- Found that some sub-major and major pairs cannot be completed under the handbook prerequisites because the prerequisites sit outside the degree, and made the planner 
  flag them instead of faking a complete plan
- Changed the filters so they apply only when I click Apply, and added a Reset filters button
- Fixed my first version, which removed the general electives because I read "the sub-major replaces the previous general electives" literally; the handbook shows the 
  24 cp block is a choice, so I restored the electives and made it either-or
- Fixed the major swap, which I had only described and not changed, so it still blocked students who had completed subjects that only counted in their old major
- Fixed the Apply button coming back, because a package of my files overwrote a one-line fix I had made locally; I now check which files a package changes before 
  unpacking it
- Fixed the Reset filters button, which looked wrong because it was a link stretched to the height of the row and underlined
- Fixed about 60 existing tests that assumed the old subject counts and the old swap rule


## AI assistance used (disclose in the report as the subject requires)
- Schema, seed data, tests and catalogue code were drafted with Claude. I reviewed, ran and committed each chunk myself.
- Code, tests and wording were drafted with Claude. I reviewed, ran and committed each chunk myself, and fixed several issues along the way (a missing template,
  wrongly placed files, edits applied to the wrong test file)
