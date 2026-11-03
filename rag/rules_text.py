"""How the app works, written as short sources the AI can quote and cite. Each entry is (ref, title, body).

These are the app's own rules, written to match what the code does (and checked by tests that read the code's constants).
They deliberately say what is simulated or unverified, so an answer built from them cannot overclaim.
"""
SOURCE = "How this app works"

RULES = [
    ("rule:degree-structure", "Degree structure and credit points",
     "The degree is the Bachelor of Computing Science (Honours), 192 credit points. It is 96 credit points of core subjects, "
     "24 credit points of honours core (Technology Research Preparation, Technology Research Methods and the 12 credit point "
     "Honours Project), 48 credit points for a major, and 24 credit points that are either a sub-major or general electives. "
     "Most subjects are 6 credit points; language subjects are 8 credit points and the Honours Project is 12."),
    ("rule:session-load", "Sessions and the 24 credit point limit",
     "A full load is 24 credit points in a session, usually four 6 credit point subjects. Sessions are Autumn (Semester 1) and "
     "Spring (Semester 2). A student can enrol in the current session and the next one only. The degree planner plans up to ten "
     "sessions ahead, and a session cannot go over 24 credit points."),
    ("rule:prerequisites", "How prerequisites work",
     "A prerequisite only counts once the subject is passed (completed). Being enrolled in it this session does not unlock the next "
     "subject for enrolment. The degree planner is looser: it accepts a prerequisite that is enrolled or planned in an earlier "
     "session, so a whole chain can be planned. 'Or' means any one of the alternatives will do, and every separate requirement must be met. "
     "Some subjects can be taken at the same time as their prerequisite (a corequisite). Some need completed credit points, for example 72 "
     "credit points completed in the degree. The app only enforces prerequisites that are subjects in this app; the UTS Handbook "
     "sometimes accepts other subjects as well, and those are shown as a note and not enforced."),
    ("rule:results-grades", "Results, marks and grades",
     "A result is a pass or a fail. Grades are HD for 85 or more, D for 75 to 84, C for 65 to 74, P for 50 to 64 and FL (fail) below 50. "
     "A pass makes the subject completed and its credit points count. A fail counts for zero credit points, ends the enrolment and "
     "makes the subject an outstanding requirement again. All marks and results in this app are simulated demonstration data, "
     "not genuine UTS academic records."),
    ("rule:retakes", "Failing and retaking a subject",
     "A failed subject can be retaken: enrol in it again in an open session, then pass it. Every attempt is kept (Failed attempt 1, "
     "Passed attempt 2) and the subject is passed only once, so its credit points are counted exactly once. A subject that needs a "
     "failed subject as a prerequisite is blocked until the failed subject is passed. A planned subject that depends on it stays in "
     "the plan, flagged with the reason, and can be rescheduled."),
    ("rule:simulator", "The semester simulator",
     "The simulated demo student can finish a semester with Complete semester or Skip to next semester. Both show a choice for every "
     "enrolled subject: Passed, Failed or No result yet, with an optional mark. No result yet records no pass and no fail, ends the "
     "enrolment, and the subject goes back to the outstanding requirements. Saving is all or nothing, and the student moves to the "
     "next session. A subject planned for a session that has passed is listed under Needs rescheduling, not deleted. The reset "
     "returns the demo student to a first-year student or to the sample two-year history."),
    ("rule:swapping", "Changing major, sub-major or electives",
     "A change of major, sub-major or the choice of electives is never blocked in the app. Before confirming, the swap page shows "
     "what would carry over and what would stop counting; nothing done is deleted from the record, and subjects that stop counting "
     "stay on the Results page. In-progress subjects that would stop counting can be withdrawn as part of the swap. In real life a change "
     "of major at UTS needs a request to the university; this app is a planning tool and shows the consequences first."),
    ("rule:swap-advice", "Swap advice and the confirmation tick",
     "Swap advice is worked out by fixed rules from the student's own record, not decided by an AI. It shows how far through the degree "
     "and major the student is, how many credit points carry over, the extra credit points and sessions needed, and a projected "
     "graduation session. The verdict is Good to switch when 6 credit points (one subject) or fewer would stop counting. It is Think "
     "carefully when two or more extra sessions are needed, 36 or more credit points would stop counting, or the student is 75 percent "
     "or more through their major with under 25 percent carrying over. Anything in between is Possible, but it costs time. For any "
     "swap that is not a good one the student must tick a box confirming they understand the extra subjects and delay before the swap "
     "goes ahead. Extra subjects mean extra tuition (HECS or otherwise); no dollar amount is shown because the app does not know the "
     "student's fees. No advice is shown when choosing a first major."),
    ("rule:count-as-electives", "Counting subjects as general electives",
     "On the general electives path, when a swap would make subjects the student has done or is doing stop counting, and the 24 credit "
     "point electives block still has room, the swap page offers to count them as general electives instead of losing them. Only subjects "
     "that would stop counting because of the swap can be offered, up to the free space. A student on a sub-major has no electives block, "
     "so no offer is made. The choices are cleared if the student leaves the electives path."),
    ("rule:sub-major-vs-major", "Sub-majors, majors and overlaps",
     "A sub-major is a separate 24 credit point requirement, not part of the 48 credit point major. A sub-major is made of core subjects "
     "(all required) and option groups (choose a number of credit points). The language sub-major needs exactly one language program of "
     "three 8 credit point subjects. A subject that is in both the major and the sub-major counts once, in the major, and is flagged. "
     "The structure of each sub-major was supplied from the UTS Handbook and has not been independently verified."),
    ("rule:assessment-load", "Assessment load (the app's estimate)",
     "Assessment load is a score from 1 to 5 that the app works out for each subject from the handbook data: how long its prerequisite "
     "chain is, how much of the marks come from an exam, how many assessments there are, whether there is a hurdle or one task worth most of "
     "the marks, and whether it is an honours or 12 credit point subject. It measures how heavy the assessment is, not how hard the content is, "
     "and it is the app's own estimate, not a UTS rating. A subject with no confirmed assessment breakdown gets no score."),
    ("rule:workload", "Session workload verdicts",
     "Each session gets a workload verdict: Light, Balanced, Heavy or Too heavy. It counts high-load subjects (assessment load 4 or 5) and "
     "crunch weeks, which are weeks with four or more deadlines or 70 percent of marks due. It also notes group-heavy and exam-heavy sessions. "
     "Due weeks are illustrative (invented), because the handbook does not publish them; the real dates are in the subject outline. A heavy "
     "session can come with a suggested move of a planned subject to a lighter session."),
    ("rule:data-sources", "Where the data comes from and what is simulated",
     "Subject names, credit points and descriptions come from the public UTS Handbook, which says its own pages are indicative; the subject "
     "outline for a session is authoritative. Assessment information is labelled indicative, historical (an older year, may have changed), "
     "unverified (no tasks shown) or invented (sample electives). Sessions offered, class times, due weeks, the students and all results are "
     "simulated or illustrative. The general electives (Introduction to Statistics and similar) are invented sample subjects. "
     "This is an independent student prototype, not an official UTS system."),
    ("rule:accounts", "Accounts and the demo student",
     "There is no public sign-up or registration, because at a real university students are given their login by admissions. The demo "
     "has one simulated student, who starts as a first-year student in Year 1, Semester 1 with no major or sub-major chosen. Only the "
     "simulated demo student can use the semester simulator and its reset."),
    ("rule:timetable", "The timetable",
     "The timetable shows the classes for a session. Each subject has a weekly lecture and, depending on the subject, tutorials or "
     "workshops with several time options. A student chooses a class for each tutorial or workshop. Clashes are allowed but drawn in red "
     "with a warning. Class times are invented for this prototype."),
]
