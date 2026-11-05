# Release 0: the core app

- **Scope:** accounts and a simulated demo student; subjects, majors and sub-majors from the handbook; enrolment with prerequisite and
  session rules; the degree planner; the timetable; failed subjects, retakes and results; changing major, sub-major or electives with
  swap advice and a confirmation; workload and assessment load; the semester simulator and demo starting points.
- **Run instructions:** see the README (`python app.py`, demo login `john.doe@student.uni.edu.au` / `Johndoe#1`).
- **Evidence:** `docs/EVIDENCE_LOG.md` (every piece of work with its hours and pull request or commit), the test suite
  (`python -m pytest -q`) and the GitHub Actions run on each pull request (tests, security lint, dependency audit).
- **Known issues:** the 2027 handbook pages could not be fetched automatically, so the prerequisites of the 76 subjects that only appear in
  sub-majors are marked unverified; session offerings, class times and due weeks are illustrative; the general electives are invented
  samples; public sign-up is switched off by design.
