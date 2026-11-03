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
|            |               | elective limits, greyed-out requirements on the Subjects page, status filter, 39 new tests                               |        |        |
| 2026-10-29 | 2 (security) and 3 (dev tools) | Enrol, withdraw and move between sessions, 24 credit point limit per session, whole-year planning,      | 1 HOUR | PR #7  |
|            |                                | CSRF on every change, ownership enforced on the server, atomic room check, 69 new tests                 |        |        |
| 2026-10-30 | 2 (security) and 3 (dev tools) | Added Ruff security rules and a dependency audit to CI; ran detect-secrets locally                      | 10 MIN | PR #8  |
| 2026-10-30 | 3 (dev tools) | Moved navigation (Subjects, Record on the left; Profile on the right), added a profile page with details, progress,      | 15 MIN | PR #9  |
|            |               | what the app stores, and the log out button, 15 new tests                                                                |        |        |
| 2026-10-30 | 3 (dev tools) | Built the degree planner: plan subjects into future sessions (add, move, remove, clear), placement rules (offering,      | 1 HOUR | PR #10 |
|            |               | 24 cp, prerequisites in an earlier session, elective limits), suggested plan, outstanding requirements, stale-plan       |        |        |
|            |               | warnings and the nav link; kept finished elective sections visible with a completion note; kept scroll position and      |        |        |
|            |               | open cards after actions; floating messages; 465 tests                                                                   |        |        |
| 2026-10-31 | 3 (dev tools) | Built the timetable: invented weekly classes (varied lecture, tutorial and workshop patterns with 5 to 10 time options   | 2 HOUR | PR #11 |
|            |               | each), weekly view for each session with a colour per subject, choose, change and drop classes, clashes allowed with     |        |        |
|            |               | a warning and shown in red, and the nav link; 83 new tests                                                               |        |        |
| 2026-11-01 | 3 (dev tools) | Added the seven other majors from my supplied data (60 more subjects) with their core and option structure, a major      | 2 HOUR | PR #12 |
|            |               | chooser (list, preview, confirm, swap), and a per-student degree that the Subjects page, enrolment, record, profile,     |        |        |
|            |               | planner and timetable all follow; the added subjects' prerequisites (alternatives, a corequisite and a credit-point      |        |        |
|            |               | condition) enforced like the originals; 695 tests                                                                        |        |        |
| 2026-11-02 | 3 (dev tools) | Added short descriptions and assessment information for every subject, read from the UTS Handbook (85 subjects) with     | 1 HOUR | PR #13 |
|            |               | 2 historical, 6 unconfirmed and 12 sample electives; each assessment structure carries a source, year and verification   |        |        |
|            |               | label; unconfirmed subjects say there is no breakdown yet; a single function decides what the AI features may use, and   |        |        |
|            |               | says "not enough context" otherwise; 56 new tests                                                                        |        |        |
| 2026-11-02 | 3 (dev tools) | Compared my prerequisites with the UTS Handbook for every subject I could read, then matched them: 34 rules added and    | 1 HOUR | PR #14 |
|            |               |7 corrected, degree-wide credit-point conditions, corequisites, the handbook's wording kept as notes where the app cannot |        |        |
|            |               |enforce it, five subject names corrected, and the demo student's history fixed; 24 new tests                              |        |        |
| 2026-11-02 | 3 (dev tools) | Fixed the prerequisite filter dropdown, which sent values the server no longer accepted, and hid the Apply button unless | 10 MIN | PR #15 |
|            |               | JavaScript is off                                                                                                        |        |        |
| 2026-11-02 | 3 (dev tools) | Added eight 24 cp sub-majors with core and option groups, a language sub-major with one chosen program of 8 cp subjects, | 2 HOUR | PR #16 |
|            |               | and a stream; 76 new subjects stored once; the 24 cp block is now a choice between a sub-major and general electives; a  |        |        |
|            |               | chooser with an impact preview; major, sub-major and electives swaps are never blocked and can withdraw in-progress      |        |        |
|            |               | subjects that stop counting; the planner and enrolment handle choose-groups in credit points and flag overlaps with the  |        |        |
|            |               | major; filters apply only on Apply with a Reset button; about 150 new tests                                              |        |        |
| 2026-11-03 | 3 (dev tools) | Added an assessment load estimate (1 to 5) worked out from the handbook assessment data, illustrative due weeks for      | 1 HOUR | PR #17 |
|            |               | every assessment, workload verdicts for each planner session and the timetable session in view (light, balanced, heavy,  |        |        |
|            |               | too heavy) with warnings and positives, and suggested moves that lighten a heavy session; kept the score inside the      |        |        |
|            |               | opened subject card only; 52 new tests                                                                                   |        |        |
| 2026-11-03 | 3 (dev tools) | Added a subject_attempts table (one row per finished attempt, never overwritten), one transactional function that        | 1 HOUR | PR #18 |
|            |               | records every result, a Results tab, and failed-subject handling in the catalogue, planner and enrolment (retakes,       |        |        |
|            |               | blocked dependants with reasons, credit points counted once); made the tests build the seeded database once per run so   |        |        |
|            |               | the suite takes under 2 minutes; 71 new tests                                                                            |        |        |
| 2026-11-03 | 3 (dev tools) | Made the current session a per-student setting that enrolment, the planner, the timetable and the profile all follow;    | 1 HOUR | PR #19 |
|            |               | built a semester simulator (Complete semester and Skip share one results screen with a Passed, Failed or No result yet   |        |        |
|            |               | choice per subject, a review step, all-or-nothing saving and a confirmed reset); planned subjects stranded in a session  |        |        |
|            |               | that has passed appear under Needs rescheduling; made the demo student start as a first-year with no major or sub-major  |        |        |
|            |               | (the two-year student is a sample history the reset can load); switched off public sign-up; added a Help guide with      |        |        |
|            |               |   step-by-step scenarios; the Results page lists the newest session first; 116 new tests                                 |        |        |
| 2026-11-04 | 1 (ethics) and 3 (dev tools) | Built swap advice worked out by rules (progress, what carries over, extra credit points and sessions,     | 1 HOUR | PR #20 |
|            |                              | projected graduation, a good, costs-time or think-carefully verdict) on every major, sub-major and        | commit 32917a0  |
|            |                              | electives swap page, with a confirmation tick the server enforces for any swap that is not a good one;    | Pushed to main  |
|            |                              | added a prompt to count subjects that would stop counting as general electives when that block has room;  |        |        |
|            |                              | built a shared read-only tool layer of ten tools for the AI features, scoped to the signed-in student;    |        |        |
|            |                              | 130 new tests

## Things that went wrong or changed

### Before PR #1: repo setup
- Changed my plan to drop the React and TypeScript goal and build a separate Flask project, because the group project belongs to another assessment
- Fixed pushing the wrong folder to a public repo by deleting it and creating a clean one
- Fixed the project being nested one folder too deep (the zip and an extra folder were committed) with a one-time force push of the single bad commit
- Fixed my first commit using a placeholder author email by amending it and force-pushing before anything else was built on it
- Changed where the project lives, moving it out of OneDrive, because syncing a virtual environment and a Git repo causes problems

### PR #1: Restructure
- Changed to a single Flask app with one module per feature instead of separate services, because it is faster to finish, easier to explain and still keeps the feature folders

### PR #2: Subject catalogue
- Changed the prerequisite rule after reviewing the UI: subjects with no rule now show "no prerequisites" instead of "not supplied"
- Changed the prerequisite badges to be neutral and gave each degree category its own colour, after thinking about what each colour should mean
- Changed HTMX to be served from the app itself instead of a CDN, so the page loads no third-party scripts and the security policy can stay strict
- Changed the colour legend into category headings that state the requirement, so the page does not rely on colour alone

### PR #3: Accounts data layer
- Changed the tests into per-feature folders, so the test layout mirrors the app
- Decided every failed login looks the same and the account locks after five failures, so responses cannot be used to find valid accounts

### PR #4: Login, sessions and the student record
- Fixed a catalogue test after the pages started using the session, because the response now varies on the cookie as well as the HTMX header
- Chose a strict content security policy, CSRF tokens on every form and same-site-only redirects from the start

### PR #5: Email login, registration and welcome screen
- Changed login from student number to email, and moved the home page to a welcome screen with a login-only catalogue
- Fixed the register page template being saved one folder too high, which broke 24 tests with "template not found"; the test suite caught it and I moved the file
- Fixed an internal server error caused by my old local database still having the old users columns, by deleting it; the tests passed because they build a fresh database each time
- Fixed several test edits that were applied to the wrong file or lost a line (missing import, missing variable, duplicated tests); the test run pointed straight at each one

### PR #6: Subject status
- Decided a prerequisite only counts once completed, so being enrolled in one this session does not unlock the next subject
- Changed completed subjects to stay visible but greyed and marked, instead of hiding them, so the degree still makes sense; the status filter lets me hide them
- Changed red to mean only "Can't enrol" and made completed requirements grey out as a whole
- Changed the demo student to have all four general electives by swapping four completed core subjects for them, so the total stayed at 96 credit points

### PR #7: Enrol, withdraw and move
- Chose to count the per-session limit in credit points (24) rather than subjects, so a 12 cp Honours subject is handled correctly
- Changed enrolling so I can plan the whole year (Autumn and Spring) at once, up to 24 credit points in each session
- Changed the room check to also run inside the insert statement, so two simultaneous requests cannot both exceed the limit
- Fixed three earlier tests that assumed Autumn-only subjects stayed available once Autumn was full

### PR #8: Security scans in CI
- Changed the demo password line to carry a stated reason, after Ruff flagged it as a hardcoded secret; I suppressed that one rule instead of hiding the finding
- Decided to postpone writing `SECURITY.md` and `ETHICS.md` until the AI features exist, so the ethics note describes what was actually built

### PR #9: Profile page and navigation
- Changed Log out from the header to the profile page, as I wanted a cleaner header with the account on the right
- Changed the nav to leave out the Degree planner and Timetable links until those pages existed, so there were no dead links
- Decided the email is shown on the profile page only, and kept it out of the session user used by every other page
- Fixed the profile page template being saved one folder too high, which broke 10 tests with "template not found"; the test run named the missing file and I moved it

### PR #10: Degree planner
- Changed the planner so a plan stays separate from enrolling, and a subject leaves the plan automatically once I enrol in it
- Changed the prerequisite check for planning to accept a subject that is planned or enrolled in an earlier session, which is looser than enrolling (needs completed); this lets me plan a whole chain ahead
- Kept planned subjects counting towards elective limits and used the same 24 credit point cap per session
- Set a ten-session planning window (five years) so a suggested plan has room to spread out; a new student's plan fits in eight
- Fixed my assumption about Honours Project B: the supplied data only links Honours Project A to Technology Research Preparation, so a suggested plan can put B before A; I did not invent a rule and recorded it as a data limitation
- Changed suggestions to use exactly the same checks as manual changes, and added a test that every suggested placement passes them
- Fixed the planner page file name (`index,html` became `index.html`) so Flask could find it
- Changed finished elective sections to stay on screen with a "you've already completed or chosen all" note instead of disappearing
- Fixed the page jumping to the top after every action by remembering the scroll position and which cards were open
- Changed confirmation and error messages into floating messages in the corner, because once I stay where I was on the page, messages at the top would be out of sight
- Decided to postpone difficulty-aware plan suggestions until after this PR, and to do the rules-based version before any AI

### PR #11: Timetable
- Changed the invented timetable so each subject follows one of four patterns (lecture and tutorial; with a workshop; with two tutorials; lecture and workshop) and every tutorial and workshop has 5 to 10 time options, so it is easier to find a time that does not clash
- Changed clash handling from refusing a clashing class to allowing it with a warning and drawing both classes in red, because I wanted to see a clash when I choose one; I updated the tests to match
- Changed the weekly view from a table to day columns, so two overlapping classes sit side by side instead of the second one being left out
- Changed lecture lengths and placement so lectures avoid each other, which cut lecture clashes from 15 pairs to 2 in Autumn, and gave each subject its own colour (shared by its lecture, tutorials and workshop)
- Fixed a bug where chosen tutorials lost their subject, because the query returned two columns both called `subject_code`; the tests showed it straight away
- Changed two queries that built their `IN (...)` lists with string formatting to filter in Python, so the security lint passes without me suppressing anything
- Changed the two seeded random generator lines to carry a stated reason after the security lint flagged them; they only produce repeatable invented data and are not used for security
- Changed withdrawing and moving a subject to remove its class choices, so the timetable never shows a class for something I am no longer enrolled in
- Changed positions and colours to use CSS classes instead of inline styles, because my security policy blocks inline styles

### PR #12: Majors
- Changed the degree data so each student has their own view of the degree: a subject now counts as major core, a major elective or not part of their degree depending on the major they chose, instead of having one fixed category
- Added the seven other majors from my supplied data (eight with Enterprise Software Development), checked that each totals exactly 48 credit points, and stored shared subjects such as Capstone once with a membership row per major
- Changed new accounts to start with no major, and to choose one from a short list, then a preview of one major's core and options, then a confirm button, so the Subjects page does not get cluttered with every major
- Changed the prerequisites from my research notes into real rules, so the added subjects behave like the original ones: "has prerequisites" with met and not-met marks, or "no prerequisites", and enforced on enrolment and in the planner
- Changed the prerequisite model so a subject can have alternatives (A or B) and a corequisite that can be taken at the same time, and added a separate credit-point condition so reaching a threshold can never stand in for a required subject
- Fixed Business Information Systems, whose core subject Data Visualisation needed a subject that is not in that major, by adding the alternative Introduction to Information Systems that my notes suggested; without it a student could never finish that major
- Decided the external prerequisite 41004 (not a subject in my data) and the leads for three original subjects stay as "not enforced" notes, because enforcing them would make a subject impossible to take or change the supplied rules
- Decided that the demo student cannot swap major because their completed subjects only count in their current major, while a new account can swap until it has enrolled in subjects only the old major has
- Changed the planner so it plans the student's own major, removes planned subjects that are not in a new major when swapping, and treats a student without a major as having 48 credit points still to plan
- Changed the timetable generator to place the original subjects first, so their class times do not move when new subjects are added
- Changed the Unlocks list to show only subjects the student could actually take
- Fixed about twenty-five existing tests that assumed every new account has the Enterprise Software Development major, or that the added prerequisites were not enforced
- Fixed the users table missing the new `major_code` column, which made hundreds of tests error until I added it to the schema file
- Fixed two planner test files that used a session constant that only exists in a third file
- Fixed the majors templates folder being named `major` instead of `majors`, so Flask could not find the pages

### PR #13: Subject descriptions and assessments
- Changed the catalogue so descriptions and assessment records are stored separately, and a subject can have several assessment structures over time, so a real outline can replace older information without deleting it
- Decided that handbook information is labelled "indicative", because the handbook says so itself, and that information from an older year is labelled historical with a warning
- Decided not to invent anything for real subjects without a confirmed breakdown: they store no tasks and tell the student they will find out when they enrol, and the older student-reported tasks for one subject are kept as an internal note only
- Changed the AI helper so it only receives confirmed or clearly labelled information and says "not enough context" otherwise, so the planner AI cannot talk about assessments I have not verified
- Fixed my plan to read every subject from the handbook after finding that six of the pages block automated access; I did not work around that and used the descriptions and historical information I was given instead
- Decided to keep the explanations of each task general to its type instead of copying handbook text

### PR #14: Prerequisites matched to the handbook
- Changed my prerequisites from the supplied rules and research leads to the UTS Handbook's requisites, after finding that my own leads were wrong for several subjects (for example Fundamentals of Interaction Design has no prerequisite at all)
- Decided to enforce only the alternatives that exist in my app and keep the full handbook wording as a visible note, because many handbook requisites accept subjects from other faculties that I do not have
- Decided not to enforce the handbook rule for Data Visualisation, because Business Information Systems makes it core but the subject it requires is not in that major, and showed it as a note instead
- Changed credit-point conditions so they can apply to the whole degree as well as to one major, and made the planner count credit planned in earlier sessions
- Fixed the demo student's history after the new rules showed that Database Fundamentals was taken before Programming 1; I swapped two subjects between sessions so his totals did not change
- Fixed five subject names that did not match the handbook, including Real Analysis, which I had called Mathematics 3
- Fixed about 40 existing tests that assumed the old rules, and added a test that every major still produces a full plan
- Decided to leave six subjects on their old rules because their handbook pages block automated access

### PR #15: Filter dropdown fix
- Fixed the prerequisite filter dropdown, which still sent the old values (`supplied` and `not_supplied`) after I changed the filter to `required` and `none`, so both options showed "Unknown prerequisite filter"
- Fixed it by editing the page, because my tests asked for the filter URLs directly and so never clicked the dropdown, which is how the stale options got past them
- Changed the Apply button to show only when JavaScript is off, because the list already updated as soon as any filter changed and the button did nothing useful

### PR #16: Sub-majors, electives choice and swaps
- Merged PR #15 into main before this one, then merged main into this branch and resolved the conflict in the filter page by keeping the newer Apply and Reset behaviour
- Changed the degree so the 24 cp block is core 96 + honours 24 + major 48 + either a sub-major or general electives, and made each choice switch the other off
- Changed the planner and enrolment so they count requirements in credit points instead of assuming 6 cp electives, which was needed for the 8 cp language subjects and for groups like "select 18 cp from six subjects"
- Added the eight sub-majors from my supplied handbook text as groups of core subjects and options, with a language sub-major where I pick exactly one language, and a stream stored as its own record with its subjects left empty because they were not supplied
- Decided that a subject in both the major and the sub-major counts once, in the major, and is flagged, because the course rules for overlaps need verifying and I did not want to double-count
- Decided swapping a major, sub-major or the electives choice is never blocked; the app shows what carries over and what stops counting first, keeps everything on the record, and counts only what counts towards the degree in the totals
- Changed the swap so in-progress subjects that stop counting can be withdrawn as part of it (ticked by default), because leaving them enrolled kept them in my session load even though they no longer counted; completed subjects are never touched
- Decided to leave language prerequisites, sequencing and the placement assessment unverified and not enforced, and to say so on the page
- Found that some sub-major and major pairs cannot be completed under the handbook prerequisites because the prerequisites sit outside the degree, and made the planner flag them instead of faking a complete plan
- Changed the filters again so they apply only when I click Apply, with a Reset filters button, because I wanted control over when the filters run; this replaced the hide-Apply-when-JavaScript-is-on change from PR #15
- Fixed my first version, which removed the general electives because I read "the sub-major replaces the previous general electives" literally; the handbook shows the 24 cp block is a choice, so I restored the electives and made it either-or
- Fixed the major swap, which I had only described and not changed, so it still blocked students who had completed subjects that only counted in their old major
- Fixed the Apply button coming back, because a package of my files overwrote a one-line fix I had made locally; I now check which files a package changes before unpacking it
- Fixed the Reset filters button, which looked wrong because it was a link stretched to the height of the row and underlined
- Fixed about 60 existing tests that assumed the old subject counts and the old swap rule

### PR #17: Assessment load, due weeks and workload
- Added an assessment load score from 1 to 5 using a visible formula (prerequisite chain depth, exam share, number of assessments, hurdle, one big task, honours or 12 cp subjects), and gave subjects with no confirmed assessment information no score instead of an average, so the AI layer cannot pretend to know them
- Decided to label the score as the app's own estimate and due weeks as illustrative everywhere they appear, and to pass the same caveats to the AI context, because the handbook publishes neither
- Changed the formula's weights after counting how many subjects landed on each score, because my first version put 70 of 100 subjects on 2 and none on 5
- Changed the crunch-week thresholds after running the verdicts over 600 random sessions, because my first numbers rated about half of all sessions heavy; the new ones spread the verdicts across all four
- Fixed my first suggestion rule, which compared combined points and so never suggested anything, because moving one subject between two sessions keeps the combined total; it now requires the moved subject to lighten this session and land somewhere lighter than this one was
- Fixed the planner offering Move choices that it would later refuse (moving a prerequisite later than something planned that needs it), after one of my new tests applied a suggestion and was refused
- Decided the AI may explain these results but never decide them, so the verdicts and suggestions are worked out by rules in code
- Changed the name from "difficulty" to "assessment load" after thinking about what the score really measures: how heavy the assessment is, not how hard the content is, so "difficulty" claimed more than I knew; I also kept the score inside the opened subject card only, so it cannot become a ranking of subjects
- Fixed one old test that said due weeks were never stored, and one that checked the exact AI context wording
- Fixed unpacking the rename on a branch that did not have the earlier workload files, which produced import errors, by checking for a key line of the earlier package before unpacking and sending one complete package instead

### PR #18: Results, attempts and failed subjects
- Added a subject_attempts table so a retake adds a new result and the old one is kept, and made one function the only way a result is recorded, so the transcript, planner, catalogue and timetable all read the same records
- Decided that a pass makes the subject completed and a fail ends the enrolment, which makes the subject an outstanding requirement again, and that a subject can only be passed once, so credit points are counted exactly once
- Decided to keep the enrolments table as the current state and attempts as the history, written together in one transaction, instead of rewriting every page to read only attempts, because it kept the change small and I added a test that the two never disagree
- Decided a planned subject that needs a failed prerequisite is flagged with the reason and kept, not deleted, so I can reschedule it after the retake
- Changed the database so it refuses impossible results (a pass graded FL, a mark over 100, repeated attempt numbers)
- Changed the tests to build the seeded database once per run and copy it for each test, which cut the suite from about 4 minutes to under 2
- Fixed a dictionary key I accidentally commented out when adding the failed-subject data to the planner, which broke 7 tests with a KeyError
- Fixed my own planner summary test that expected the wrong wording, and an isolation test that forgot the demo student has his own Programming 1

### PR #19: Semester simulator and a first-year demo student
- Changed the current session from one fixed constant to a per-student setting, so the planner window, the open sessions, the timetable and the profile all follow it and the simulator can move one student forward without touching the others
- Decided Complete semester and Skip are one results screen with a Passed, Failed or No result yet choice per subject, after reconsidering my first idea that Skip should only work with nothing enrolled; "No result yet" records no attempt and ends the enrolment, so advancing the calendar never invents a pass or fail
- Decided finishing a semester is one transaction (all results, the ended enrolments and the new session together), and wrote a test that forces a failure part-way and checks nothing changed
- Decided only the demo student can use the simulator or reset it, and that reset only ever touches that one account's records
- Changed the mark check into one shared function so the simulator and the results code apply the same rule (a mark must agree with the result)
- Decided the demo student starts as a first-year student and kept the old two-year student as a sample history the reset can load, because a fresh student lets people create their own scenarios while the sample history is still useful for exploring blocked subjects and sub-majors
- Decided to switch off public sign-up, because at a real university students get their login from admissions, and kept the registration code behind a setting for development instead of deleting it
- Decided the Results page lists the newest session first, because it is the page students open to see their latest results, and left Record oldest first as the degree-history view
- Changed the tests to get the two-year student and sign-up through environment settings instead of rewriting about 150 tests, and added separate tests for the real defaults
- Wrote the help guide's scenarios as tests that follow their steps through the app, so the guide cannot say something the app no longer does
- Fixed a gap my own tests exposed: a subject planned for a session that had just passed vanished from the planner, so I added a Needs rescheduling section with the reason, and Suggest a plan now re-plans those subjects
- Fixed my first version of the fresh demo student, which had the Enterprise Software Development major already chosen; a real first-year student has not picked a major yet, so the fresh student now starts with no major or sub-major and chooses both from the Subjects page
- Fixed the reset command, which rebuilt the database with the wrong starting student after I added the two profiles
- Fixed my first test helper, which looked for a CSRF token on a page with no form, and a reset test that enrolled the student in an Autumn-only subject in Spring
- Fixed several weak assertions in my first test drafts (ones that could never fail) by making them exact

### Swap advice, count-as-electives and the AI tool layer (pushed directly to main)
- Decided the swap verdict is worked out by fixed rules from the student's own record and the AI will only explain it, because a verdict that could change between runs cannot be tested or trusted, and the student must be able to see why
- Decided to keep the final yes with the student: any swap that is not a good one needs a tick box that the server checks, so a missing or wrong tick refuses the swap and changes nothing
- Decided to show extra credit points, sessions and a projected graduation session but no dollar amount, because every extra subject costs tuition whether or not it is paid through HECS and the app does not know the student's fees
- Calculated the advice on a copy of the data that is rolled back, so asking for advice can never change a major, a plan or a result, and wrote a test that checks nothing moved
- Added a prompt to count subjects that would stop counting as general electives, after thinking about how real degrees work: a subject that does not count in a new major can still fill a free elective slot
- Decided the prompt appears only on the general electives path and only while that block has room, only offers subjects that would stop counting because of the swap, and is validated on the server, because counting any real subject as an elective needs the handbook's rule for what electives may be
- Decided every AI tool is read-only and the student is chosen by the server from the session, never by the model; no tool takes a user id and an unknown argument is refused, so a prompt injection cannot ask about another student
- Decided to check every tool argument against a schema (type, format, allowed values, length) before anything runs, and tested SQL-injection and path-traversal strings
- Fixed a bug in my first subject tool, which flattened "(A or B) and C" prerequisites into one list of alternatives and would have told the AI wrong rules, by using the same requirement groups the pages use
- Fixed my first version, which showed "Swap advice" and a table of zeros when a first-year student was choosing their first major; a first choice has nothing to swap from, so the box is now hidden for it and a short note replaces the numbers when nothing that counts has been done yet; I found it by looking at the page as a new student, because my tests only checked that the verdict was "good"
- Fixed four earlier swap tests that now needed the confirmation tick, a prerequisite test that assumed a subject outside the degree was an error when it is correctly reported as not part of the degree, and four mistakes in my first count-as-electives tests (a subject with an unmet prerequisite, subjects that would not really stop counting, a core subject that always counts, and a message read from the wrong page)
- Fixed my own mistake of pushing this work straight to main: my command to create a branch failed because that branch name already existed from an earlier attempt, and I did not check which branch I was on before committing
- Checked main afterwards by running the whole suite (1303 passed) and the GitHub Actions run, and turned on branch protection (a pull request and passing checks are required, with no bypass for me as the owner), so a direct push to main is now refused
- Changed my routine to print the current branch name before any commit and to stop if a "fatal" line appears

## AI assistance used (disclose in the report as the subject requires)
- Schema, seed data, tests and catalogue code were drafted with Claude. I reviewed, ran and committed each chunk myself.
- Code, tests and wording were drafted with Claude. I reviewed, ran and committed each chunk myself, and fixed several issues along the way (a missing template,
  wrongly placed files, edits applied to the wrong test file)
