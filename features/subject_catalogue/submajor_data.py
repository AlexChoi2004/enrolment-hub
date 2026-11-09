"""Sub-majors: 24 cp blocks of the degree, each with compulsory (core) subjects and selectable options.

SUPPLIED STRUCTURE: the sub-majors below (codes, names, which subjects are core or options, how many credit points
to select) were supplied from the UTS Handbook text, and checked against the Handbook pages on 8 November 2026 (tests/features/subject_catalogue/test_handbook_check.py).
NOT VERIFIED: prerequisites, descriptions, assessments and session offerings of the subjects that exist only in these
sub-majors. Their offerings are illustrative; the others are marked "prerequisites not verified" and not enforced.
Subjects are stored once in the subject catalogue; membership of a sub-major is stored separately.
"""
import zlib

SOURCE_NOTE = "Structure checked against the UTS Handbook page for this sub-major (2027; Humanitarian Engineering is the 2026 page) on 8 November 2026."


def _sessions(code):
    """Illustrative offering, repeatable for a code (the handbook pages for these subjects were not read)."""
    n = zlib.crc32(code.encode())
    return "Autumn" if n % 4 == 0 else "Spring" if n % 4 == 1 else "Both"


# Subjects that exist only because a sub-major lists them. (code, name, credit points)
SUBMAJOR_ONLY = [
    ("37242", "Introduction to Optimisation", 6),
    ("37345", "Quantitative Management Practice", 6),
    ("43029", "Introduction to Humanitarian Engineering", 6),
    ("99200", "Intercultural Communication", 6),
    ("977917", "In-country Contemporary Society Study", 6),  # the code is as supplied (six digits); verify it
    ("97901", "International Internship", 6),
    ("41130", "Professional Practice Studio", 6),
    ("48080", "Introduction to Innovation", 6),
    ("81529", "Futuring for Innovation with Impact", 6),
    ("81546", "Innovation in Complex Systems", 6),
    ("81547", "Leading Creative Innovation", 6),
    ("40005", "Advanced iOS Development", 6),
    ("40006", "iOS Industry Studio", 6),
    ("37335", "Differential Equations", 6),
    ("37495", "Statistical Design and Models for Evaluation Studies", 6),
    ("37363", "Stochastic Processes and Financial Mathematics", 6),
    ("37336", "Vector Calculus and Partial Differential Equations", 6),
]

# Language programs of the LOTE sub-major: code -> (language, [(subject code, name)]). Every subject is 8 cp.
LANGUAGES = {
    "CBK90494": ("Chinese", [
        ("97116", "Chinese Business and Administrative Language"), ("97113", "Chinese Culture and Heritage"),
        ("97111", "Chinese Festivals and Ceremonies"), ("97101", "Chinese Language and Culture 1"),
        ("97102", "Chinese Language and Culture 2"), ("97103", "Chinese Language and Culture 3"),
        ("97104", "Chinese Language and Culture 4"), ("97105", "Chinese Language and Culture 5"),
        ("97106", "Chinese Language and Culture 6"), ("97109", "Communicating About Chinese Media"),
        ("97114", "Developing Chinese Reading and Writing Skills 1"),
        ("97115", "Developing Chinese Reading and Writing Skills 2"), ("97112", "Language in Chinese Screen Studies"),
    ]),
    "CBK90497": ("French", [
        ("97409", "Francophone Cultures of Consumption"), ("97407", "Francophone Identities in Conflict"),
        ("97401", "French Language and Culture 1"), ("97402", "French Language and Culture 2"),
        ("97403", "French Language and Culture 3"), ("97404", "French Language and Culture 4"),
        ("97405", "French Language and Culture 5"), ("97406", "French Language and Culture 6"),
        ("97410", "Places and Spaces of the Francophone World"), ("97408", "Show and Tell: Francophone Cultures on Display"),
    ]),
    "CBK90499": ("German", [
        ("97607", "German Film"), ("97601", "German Language and Culture 1"), ("97602", "German Language and Culture 2"),
        ("97603", "German Language and Culture 3"), ("97604", "German Language and Culture 4"),
        ("97606", "German Literature"), ("97608", "German Popular Music"), ("97605", "German Today"),
    ]),
    "CBK90500": ("Italian", [
        ("97801", "Italian Language and Culture 1"), ("97802", "Italian Language and Culture 2"),
        ("97803", "Italian Language and Culture 3"), ("97804", "Italian Language and Culture 4"),
        ("97808", "Italian Language and the Arts"), ("97806", "Italian Popular Culture"),
        ("97807", "Italophone Literature(s)"), ("97805", "Italy and Migration"),
    ]),
    "CBK90495": ("Japanese", [
        ("97207", "Japanese Films and Popular Culture"), ("97201", "Japanese Language and Culture 1"),
        ("97202", "Japanese Language and Culture 2"), ("97203", "Japanese Language and Culture 3"),
        ("97204", "Japanese Language and Culture 4"), ("97205", "Japanese Language and Culture 5"),
        ("97206", "Japanese Language and Culture 6"), ("97208", "Japanese Language and Identity"),
        ("97209", "Japanese Media and Current Issues"), ("97210", "Transcultural Communication in Japanese"),
    ]),
    "CBK90498": ("Spanish", [
        ("97510", "Diaspora of the Hispanic Imagination"), ("97507", "Human Rights in Hispanophone Societies"),
        ("97509", "Innocence and Experience in Hispanophone Societies"), ("97501", "Spanish Language and Culture 1"),
        ("97502", "Spanish Language and Culture 2"), ("97503", "Spanish Language and Culture 3"),
        ("97504", "Spanish Language and Culture 4"), ("97505", "Spanish Language and Culture 5"),
        ("97506", "Spanish Language and Culture 6"), ("97508", "US Latin American Relations"),
    ]),
}
LANGUAGE_CP = 8

# Streams are lists of subjects chosen from. CBK92069 is used by the Humanitarian Engineering sub-major and by the general electives choice.
STREAMS = [
    ("CBK92069", "Transdisciplinary Electives", 6, "Choose 6 credit points (one subject) from these eight subjects, as the Handbook lists them for 2027."),
]
TD_SUBJECTS = [
    ("95002", "TD: Reframing, remixing, reimagining society"), ("95003", "TD: Sustainability in an interconnected world"),
    ("95004", "TD: Technologies reimagined in a complex world"), ("95005", "TD: Shaping technologies that shape us"),
    ("95006", "TD: Envisioning futures worth wanting"), ("95007", "TD: Pathways to societal transitions"),
    ("95008", "TD: Transdisciplinary action lab"), ("95009", "TD: Change-making for social impact"),
]
STREAM_SUBJECTS = {"CBK92069": [code for code, _ in TD_SUBJECTS]}
# Every transdisciplinary elective has the same academic requisite: at least 36 credit points completed in a bachelor's degree (as supplied, 2027 Handbook).
# (subject, major, minimum): no major means credit points completed anywhere in the student's degree.
TD_CREDIT_REQUIREMENTS = [(code, None, 36) for code, _ in TD_SUBJECTS]
TD_REQUISITE_NOTE = "Academic requisite from the 2027 Handbook (as supplied): at least 36 credit points completed in a bachelor's degree."
# Availability from each subject's 2027 Handbook page (as supplied on 9 November 2026): (the Autumn or Spring session the app plans it in,
# any other session the Handbook lists, which the app does not model). The February, July and December sessions are noted, not planned.
TD_AVAILABILITY = {
    "95002": ("Autumn", "July session (block)"), "95003": ("Spring", "February session (block)"), "95004": ("Spring", None),
    "95005": ("Autumn", "July session (block)"), "95006": ("Autumn", None), "95007": ("Spring", None),
    "95008": ("Autumn", None), "95009": ("Spring", "December session (block)"),
}

# Subjects that were not in the app before, as full rows for the subjects table.
SUBJECTS = (
    [(code, name, cp, "major_other", "Both" if code in ("48080", "81529", "81546", "81547") else _sessions(code), "", 0)
     for code, name, cp in SUBMAJOR_ONLY]
    + [(code, name, LANGUAGE_CP, "major_other", _sessions(code), "", 0)
       for _, (_, subjects) in LANGUAGES.items() for code, name in subjects]
    # Transdisciplinary electives: they count in the stream of the sub-major that lists them, or as the 6 cp transdisciplinary elective of the general electives choice
    + [(code, name, 6, "td_elective", TD_AVAILABILITY[code][0], "", 0) for code, name in TD_SUBJECTS]
)

# (code, name, note, groups). A group is ("core" | "choose", label, credit points, [subject codes], stream code or None,
# language program code or None). Core groups: complete every subject. Choose groups: select that many credit points.
SUBMAJORS = [
    ("SMJ10165", "Applied and Industrial Optimisation", "", [
        ("core", "Core", 18, ["37233", "37242", "37345"], None, None),
        ("choose", "Options", 6, ["68416", "37161"], None, None),
    ]),
    ("SMJ10196", "Humanitarian Engineering", "The Handbook page for this sub-major is the 2026 version.", [
        ("core", "Core", 12, ["43029", "99200"], None, None),
        ("choose", "Transdisciplinary electives (stream CBK92069)", 6, [], "CBK92069", None),
        ("choose", "Options", 6, ["977917", "97901", "41130"], None, None),
    ]),
    ("SMJ10157", "Information Security", "", [
        ("core", "Core", 6, ["41181"], None, None),
        ("choose", "Options", 18, ["48730", "41180", "41185", "41183", "41184", "41182"], None, None),
    ]),
    ("SMJ10156", "Innovation and Entrepreneurship", "", [
        ("core", "Core", 24, ["48080", "81529", "81546", "81547"], None, None),
    ]),
    ("SMJ10190", "iOS Industry", "", [
        ("core", "Core", 18, ["40005", "40006", "41889"], None, None),
        ("choose", "Options", 6, ["31777", "41001", "31260", "41020", "40007"], None, None),
    ]),
    ("SMJ10167", "Mathematical Analysis Extension",
     "The Handbook lists two groups of options: choose 6 credit points from the first group and 18 from the second.", [
        ("choose", "Options group 1", 6, ["35005", "37262"], None, None),
        ("choose", "Options group 2", 18, ["37335", "37242", "37345", "37495", "37363", "37336"], None, None),
    ]),
    ("SMJ10166", "Statistical Analysis", "", [
        ("core", "Core", 12, ["37161", "37252"], None, None),
        ("choose", "Options", 12, ["37242", "37262", "37373", "37495", "37363"], None, None),
    ]),
    ("SMJ09035", "Language Other Than English (LOTE)",
     "Choose ONE language program and take 24 cp (three 8 cp subjects) from it. Language-level prerequisites, the order "
     "of the subjects and the language level assessment for first-time students are not verified, so they are not enforced.", [
        ("choose", f"{language} ({code})", 24, [s for s, _ in subjects], None, code)
        for code, (language, subjects) in LANGUAGES.items()
    ]),
]
