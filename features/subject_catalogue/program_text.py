"""Short descriptions of majors and sub-majors, and a link to the official Handbook page for each.

The Handbook does not allow automated reading, so a summary is written by hand, in our own words, from the Handbook's overview text; it is
never copied. Where no summary has been added yet, the page says so and links to the Handbook, so nothing is ever invented.
The pages are indicative: the Handbook for the student's own year is the authority.
"""
HANDBOOK = "https://coursehandbook.uts.edu.au/aos"
HANDBOOK_YEAR = {"SMJ10196": 2026}  # the Handbook's page for this sub-major is for 2026; every other page is for 2027
CODES = (
    "MAJ10053", "MAJ02080", "MAJ02900", "MAJ02092", "MAJ03519", "MAJ01156", "MAJ03445", "MAJ02901",
    "SMJ10165", "SMJ10188", "SMJ10196", "SMJ10157", "SMJ10156", "SMJ10190", "SMJ10166", "SMJ10167", "SMJ09035",
)

SUMMARIES = {
    "MAJ10053": {
        "summary": "Covers the computing techniques behind artificial intelligence and data analytics, which are growing quickly in the technology industry. "
                   "Students prepare and structure data sets, use computational methods to analyse data and train AI models, and then build, tune and "
                   "check algorithms for both fields.",
        "retrieved_on": "2026-11-08",
    },
}


def handbook_url(code):
    """The official page for this major or sub-major, or None for a code we do not know."""
    if code not in CODES:
        return None
    return f"{HANDBOOK}/{HANDBOOK_YEAR.get(code, 2027)}/{code}"


def summary_of(code):
    """The summary written for this code: {'summary', 'retrieved_on'} or None if none has been added yet."""
    return SUMMARIES.get(code)
