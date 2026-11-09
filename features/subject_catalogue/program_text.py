"""Short descriptions of majors and sub-majors, and a link to the official Handbook page for each.

The Handbook does not allow automated reading, so a summary is written by hand, in our own words, from the Handbook's overview text; it is
never copied. Where no summary has been added yet, the page says so and links to the Handbook, so nothing is ever invented.
The pages are indicative: the Handbook for the student's own year is the authority.
"""
HANDBOOK = "https://coursehandbook.uts.edu.au/aos"
HANDBOOK_YEAR = {"SMJ10196": 2026}  # the Handbook's page for this sub-major is for 2026; every other page is for 2027
CODES = (  # the eight majors and eight sub-majors of this degree, as the Handbook lists them (SMJ10188 is not in its list for this degree)
    "MAJ10053", "MAJ02080", "MAJ02900", "MAJ02092", "MAJ03519", "MAJ01156", "MAJ03445", "MAJ02901",
    "SMJ10165", "SMJ10196", "SMJ10157", "SMJ10156", "SMJ10190", "SMJ10166", "SMJ10167", "SMJ09035",
)
SUBJECT_URL = "https://coursehandbook.uts.edu.au/subject"
# The Humanitarian Engineering sub-major's Handbook page is the 2026 version, so its own subjects link to 2026 pages (as supplied).
SUBJECT_YEAR = {"43029": 2026, "99200": 2026, "977917": 2026, "97901": 2026, "41130": 2026}
STREAM_CODES = ("CBK92069",)  # CBK92186 (free electives) has no Handbook page supplied, so it has no link

SUMMARIES = {
    "MAJ10053": {"summary": "Covers the computing techniques behind artificial intelligence and data analytics, which are growing quickly in the technology industry. "
                            "Students prepare and structure data sets, use computational methods to analyse data and train AI models, and then build, tune and "
                            "check algorithms for both fields.", "retrieved_on": "2026-11-08"},
    "MAJ02080": {"summary": "Teaches how to design information and communication technology for many kinds of business activity, from customer-facing operations and "
                            "sharing knowledge to collaboration and strategy, alongside organisation theory, accounting and project management. It prepares students "
                            "to manage how technology fits into business and society, and to lead its introduction.", "retrieved_on": "2026-11-08"},
    "MAJ02900": {"summary": "Builds the knowledge and technical skills industry expects of a cybersecurity professional, including investigating and fighting cybercrime. "
                            "Students learn to find, analyse and manage security problems across areas such as digital forensics, software weaknesses, secure databases "
                            "and operating systems, website security, secure network design, risk assessment and responding to incidents.", "retrieved_on": "2026-11-08"},
    "MAJ03519": {"summary": "An introduction to building software applications, applying ideas from computer science, project management and other fields to produce "
                            "business solutions with known qualities. Students also learn to direct their programming towards systems that deliver the functions and "
                            "the quality a business needs.", "retrieved_on": "2026-11-08"},
    "MAJ02092": {"summary": "Looks at how digital technology shapes everyday life, and how to design interactions that work within complex social and physical settings. "
                            "Students learn human-centred ways to design and build technology that is enjoyable, effective, ethical, sustainable and responsible, and gain "
                            "the practical skills to turn design ideas into working systems.", "retrieved_on": "2026-11-08"},
    "MAJ03445": {"summary": "Gives students the knowledge and skills to design networks and build applications on them, with a focus on technology services. They study "
                            "how the internet is designed, including its architecture, protocols and components, together with the software tools and programming methods "
                            "for building well-designed, secure networks, through both future network design and practical applications and services.", "retrieved_on": "2026-11-08"},
    "MAJ02901": {"summary": "Studies how quantum mechanics can power new ways of processing information, a field expected to outperform classical approaches. The major "
                            "combines computer science, mathematics and physics, from basic ideas to current topics such as quantum algorithms, computer architectures and "
                            "programming, and prepares students for quantum technology careers, analysis-heavy industries, start-ups and research.", "retrieved_on": "2026-11-08"},
    "SMJ10196": {"summary": "Introduces key ideas in humanitarian engineering, building on the Engineers without Borders Challenge, and develops intercultural and "
                            "cross-discipline collaboration through work with partners and students from different backgrounds, so students can use engineering to make "
                            "positive change. Students choose a transdisciplinary elective; the Handbook recommends two of them (95009 and 95003). This is the 2026 page.",
                 "retrieved_on": "2026-11-08"},
    "SMJ10190": {"summary": "Builds skills in designing and developing mobile apps with Apple's iOS frameworks, supported by hands-on practice in iOS studios. Students "
                            "need Programming Fundamentals or Programming 1, and Database Fundamentals or equivalent, before starting, and are advised to take "
                            "Fundamentals of Interaction Design.", "retrieved_on": "2026-11-08"},
    "SMJ09035": {"summary": "Lets students build communicative competence in a language other than English by taking three consecutive 8 credit point subjects from one "
                            "language program (Chinese, French, German, Italian, Japanese or Spanish). It takes three semesters, so starting in Autumn of second year is "
                            "advised, and students new to a language at UTS sit a placement assessment.", "retrieved_on": "2026-11-08"},
}
# Programs whose Handbook page has a structure but no overview paragraph (so there is nothing to summarise, and the page says so).
NO_OVERVIEW = frozenset({"MAJ01156", "SMJ10165", "SMJ10157", "SMJ10156", "SMJ10167", "SMJ10166"})
# One-line notes the Handbook's overview gives about a program, in our own words.
NOTES = {"MAJ03445": "The Handbook advises students planning this major to take 41039 Programming 1 rather than 48023 Programming Fundamentals."}


def handbook_url(code):
    """The official page for this major or sub-major, or None for a code we do not know."""
    return aos_url(code) if code in CODES else None


def summary_of(code):
    """The summary written for this code: {'summary', 'retrieved_on'} or None if none has been added yet."""
    return SUMMARIES.get(code)


def subject_handbook_url(code):
    """The official page for a real subject (a 5 or 6 digit code), or None for anything else, such as the invented sample electives."""
    import re
    if not re.fullmatch(r"\d{5,6}", code or ""):
        return None
    return f"{SUBJECT_URL}/{SUBJECT_YEAR.get(code, 2027)}/{code}"


def aos_url(code, year=None):
    """The official overview page of a major, sub-major or stream; None for a code that was not supplied."""
    if code not in CODES and code not in STREAM_CODES:
        return None
    return f"{HANDBOOK}/{year or HANDBOOK_YEAR.get(code, 2027)}/{code}"


def has_no_overview(code):
    return code in NO_OVERVIEW


def note_of(code):
    return NOTES.get(code)
