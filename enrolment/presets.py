"""The demo student's starting points ("presets"): quick ways to reach the situation a reviewer wants to test.

Each preset is complete data: when the student started, which session they are in, their major and sub-major, every finished
session (with passes and fails), what they are enrolled in now, and anything already planned. They are invented, but they follow
the same rules as everything else (prerequisites, offerings, 24 credit points a session), and tests check every one of them.
Choosing one from Reset wipes the demo student's simulated records and loads it, so nobody has to pass semester after semester
to reach a late-degree situation.
"""
from accounts.seed import DEMO_MAJOR_CODE, DEMO_SUBMAJOR_CODE

AUTUMN_2027 = "Autumn 2027"  # the app's "now": the first session of the demonstration

# The two-year history that earlier versions called the sample. Kept exactly as it was.
SAMPLE_HISTORY = [
    ("Autumn 2025", [("41039", "passed"), ("33130", "passed"), ("31268", "passed"), ("48080", "passed")]),
    ("Spring 2025", [("48024", "passed"), ("33230", "passed"), ("31269", "passed"), ("81529", "passed")]),
    ("Autumn 2026", [("31251", "passed"), ("41025", "passed"), ("41078", "passed"), ("31271", "passed")]),
    ("Spring 2026", [("48433", "passed"), ("31282", "passed"), ("81546", "passed"), ("81547", "passed")]),
]

PRESETS = {
    "fresh": {
        "title": "A first-year student",
        "summary": "Year 1, Semester 1. No major or sub-major chosen, no results, nothing enrolled.",
        "good_for": ["Choosing a major, then a sub-major or electives", "Your first enrolments and the timetable", "Planning the whole degree from scratch"],
        "commencement": AUTUMN_2027, "current": AUTUMN_2027, "major": None, "submajor": None,
        "history": [], "enrolled": [], "plan": [],
    },
    "sample": {
        "title": "Two years in, halfway through the major",
        "summary": "Year 3, Semester 1. 62% through the Enterprise Software Development major, the Innovation and Entrepreneurship sub-major "
                   "finished, 16 subjects passed and 4 in progress.",
        "good_for": ["Swap advice that says \"Possible, but it costs time\"", "Counting a sub-major's subjects as electives",
                     "A Heavy session and its suggested move", "Blocked and available subjects", "Completing semesters and rolling them back"],
        "commencement": "Autumn 2025", "current": AUTUMN_2027, "major": DEMO_MAJOR_CODE, "submajor": DEMO_SUBMAJOR_CODE,
        "history": SAMPLE_HISTORY, "enrolled": ["41026", "31272", "32144", "41040"], "plan": [],
    },
    "late": {
        "title": "Late in the major (about 90% through)",
        "summary": "Year 3, Semester 2. 88% through the Enterprise Software Development major (two of its option subjects in progress), "
                   "20 subjects passed and 4 in progress.",
        "good_for": ["Swap advice that says \"Think carefully\" and needs the confirmation tick", "The projected graduation session moving later",
                     "Asking the AI advisor to explain a risky swap"],
        "commencement": "Autumn 2025", "current": "Spring 2027", "major": DEMO_MAJOR_CODE, "submajor": DEMO_SUBMAJOR_CODE,
        "history": SAMPLE_HISTORY + [(AUTUMN_2027, [("41026", "passed"), ("31272", "passed"), ("32144", "passed"), ("41040", "passed")])],
        "enrolled": ["41052", "32113", "32931", "41079"], "plan": [],
    },
    "failed": {
        "title": "A failed prerequisite",
        "summary": "Year 2, Semester 1. Programming 2 was failed last session and has not been retaken yet; Data Structures and Algorithms is "
                   "planned but blocked by it.",
        "good_for": ["A planned subject flagged because its prerequisite was failed", "Add retake to plan, enrol in the retake, then pass it",
                     "Credit points counted once across two attempts", "Rolling back the semester that finished it"],
        "commencement": "Autumn 2026", "current": AUTUMN_2027, "major": DEMO_MAJOR_CODE, "submajor": DEMO_SUBMAJOR_CODE,
        "history": [
            ("Autumn 2026", [("41039", "passed"), ("33130", "passed"), ("31268", "passed"), ("48080", "passed")]),
            ("Spring 2026", [("48024", "failed"), ("33230", "passed"), ("31269", "passed"), ("81529", "passed")]),
        ],
        "enrolled": ["31265", "37181", "41025"], "plan": [("31251", "Spring 2027")],
    },
}
DEFAULT_PRESET = "fresh"


def preset_state(key):
    """(commencement session, current session, major, sub-major) for a preset."""
    p = PRESETS[key]
    return p["commencement"], p["current"], p["major"], p["submajor"]
