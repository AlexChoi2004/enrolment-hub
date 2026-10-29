"""Seed data for C09119 Bachelor of Computing Science (Honours), ESD major.

SUPPLIED REFERENCE DATA: subject codes, names, credit points, categories and the
12 prerequisite rules below were supplied for this project. They are NOT
independently verified against the official handbook.

ILLUSTRATIVE DATA: sessions_offered (all subjects) and the SYN general electives
are invented for this prototype. Real subject descriptions are left empty on
purpose rather than invented.
"""

COURSE = {
    "code": "C09119",
    "name": "Bachelor of Computing Science (Honours)",
    "major_code": "MAJ03519",
    "major_name": "Enterprise Software Development",
    "handbook_year": 2027,
}

# (category, label, required credit points, sort order)
CATEGORIES = [
    ("core", "Core subjects", 96, 1),
    ("honours_core", "Honours core", 24, 2),
    ("major_core", "Major core", 30, 3),
    ("major_elective", "Major electives", 18, 4),
    ("general_elective", "General electives", 24, 5),
]
TOTAL_CREDIT_POINTS = 192

# (code, name, credit points, category, sessions offered, description, is_synthetic)
SUBJECTS = [
    # Core: 16 x 6 = 96 cp
    ("33130", "Mathematics 1", 6, "core", "Both", "", 0),
    ("37181", "Discrete Mathematics", 6, "core", "Both", "", 0),
    ("41039", "Programming 1", 6, "core", "Both", "", 0),
    ("31265", "Communication for IT Professionals", 6, "core", "Both", "", 0),
    ("33230", "Mathematics 2", 6, "core", "Both", "", 0),
    ("31269", "Business Requirements Modelling", 6, "core", "Both", "", 0),
    ("31271", "Database Fundamentals", 6, "core", "Both", "", 0),
    ("48024", "Programming 2", 6, "core", "Both", "", 0),
    ("31268", "Web Systems", 6, "core", "Both", "", 0),
    ("41092", "Network Fundamentals", 6, "core", "Both", "", 0),
    ("41078", "Computing Science Studio 1", 6, "core", "Autumn", "", 0),
    ("41080", "Theory of Computing Science", 6, "core", "Spring", "", 0),
    ("43030", "Professional Practice in Computing", 6, "core", "Both", "", 0),
    ("31251", "Data Structures and Algorithms", 6, "core", "Both", "", 0),
    ("41079", "Computing Science Studio 2", 6, "core", "Spring", "", 0),
    ("31272", "Project Management and the Professional", 6, "core", "Autumn", "", 0),
    # Honours core: 6 + 6 + 12 = 24 cp
    ("32144", "Technology Research Preparation", 6, "honours_core", "Autumn", "", 0),
    ("32931", "Honours Project A", 6, "honours_core", "Spring", "", 0),
    ("31482", "Honours Project B", 12, "honours_core", "Autumn", "", 0),
    # Major core: 5 x 6 = 30 cp
    ("41025", "Introduction to Software Development", 6, "major_core", "Both", "", 0),
    ("31282", "Systems Testing and Quality Management", 6, "major_core", "Spring", "", 0),
    ("41026", "Advanced Software Development", 6, "major_core", "Autumn", "", 0),
    ("48433", "Software Architecture", 6, "major_core", "Spring", "", 0),
    ("41759", "Capstone", 6, "major_core", "Autumn", "", 0),
    # Major electives: choose 3 x 6 = 18 cp
    ("41052", "Advanced Algorithms", 6, "major_elective", "Spring", "", 0),
    ("32113", "Advanced Database", 6, "major_elective", "Spring", "", 0),
    ("31777", "Advanced Interaction Design", 6, "major_elective", "Autumn", "", 0),
    ("41889", "Application Development in the iOS Environment", 6, "major_elective", "Autumn", "", 0),
    ("31927", "Application Development with .NET", 6, "major_elective", "Spring", "", 0),
    ("41001", "Cloud Computing and Software as a Service", 6, "major_elective", "Autumn", "", 0),
    ("31260", "Fundamentals of Interaction Design", 6, "major_elective", "Both", "", 0),
    ("41113", "Software Development Studio", 6, "major_elective", "Spring", "", 0),
    ("41040", "Introduction to Artificial Intelligence", 6, "major_elective", "Autumn", "", 0),
    # General electives: SYNTHETIC. Need 24 cp = 4 subjects.
    ("SYN101", "Introduction to Statistics", 6, "general_elective", "Both", "Illustrative synthetic subject: descriptive statistics and probability basics.", 1),
    ("SYN102", "Financial Accounting Basics", 6, "general_elective", "Autumn", "Illustrative synthetic subject: reading and preparing simple financial statements.", 1),
    ("SYN103", "Marketing Principles", 6, "general_elective", "Spring", "Illustrative synthetic subject: how products are positioned and promoted.", 1),
    ("SYN104", "Introduction to Psychology", 6, "general_elective", "Both", "Illustrative synthetic subject: core ideas in human behaviour.", 1),
    ("SYN105", "Creative Writing", 6, "general_elective", "Autumn", "Illustrative synthetic subject: short-form fiction and feedback workshops.", 1),
    ("SYN106", "Design Thinking for Sustainability", 6, "general_elective", "Spring", "Illustrative synthetic subject: human-centred design for sustainable outcomes.", 1),
    ("SYN107", "Introduction to Economics", 6, "general_elective", "Both", "Illustrative synthetic subject: supply, demand and market behaviour.", 1),
    ("SYN108", "Data Visualisation", 6, "general_elective", "Autumn", "Illustrative synthetic subject: communicating data with charts.", 1),
    ("SYN109", "Linear Optimisation", 6, "general_elective", "Spring", "Illustrative synthetic subject: modelling and solving optimisation problems.", 1),
    ("SYN110", "Entrepreneurship Fundamentals", 6, "general_elective", "Both", "Illustrative synthetic subject: turning ideas into small ventures.", 1),
    ("SYN111", "Digital Media Production", 6, "general_elective", "Spring", "Illustrative synthetic subject: planning and producing short digital media.", 1),
    ("SYN112", "Technology, Society and Ethics", 6, "general_elective", "Autumn", "Illustrative synthetic subject: social impact of technology.", 1),
]

# (subject_code, prerequisite_code). The 12 supplied rules, converted from names.
PREREQUISITES = [
    ("33230", "33130"),  # Mathematics 2 <- Mathematics 1
    ("48024", "41039"),  # Programming 2 <- Programming 1
    ("31251", "48024"),  # Data Structures and Algorithms <- Programming 2
    ("41025", "41039"),  # Introduction to Software Development <- Programming 1
    ("41026", "41025"),  # Advanced Software Development <- Introduction to Software Development
    ("31282", "31269"),  # Systems Testing and Quality Management <- Business Requirements Modelling
    ("48433", "48024"),  # Software Architecture <- Programming 2
    ("41079", "41078"),  # Computing Science Studio 2 <- Computing Science Studio 1
    ("32931", "32144"),  # Honours Project A <- Technology Research Preparation
    ("41052", "31251"),  # Advanced Algorithms <- Data Structures and Algorithms
    ("32113", "31271"),  # Advanced Database <- Database Fundamentals
    ("41001", "48024"),  # Cloud Computing and SaaS <- Programming 2
]