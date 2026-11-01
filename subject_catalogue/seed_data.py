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
    # Where subjects that belong only to other majors are stored. Never shown as a section.
    ("major_other", "Other majors", 0, 6),
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



# --- Other majors -------------------------------------------------------------------------
# SUPPLIED STRUCTURE: the majors below (codes, names, core and option lists, and the credit points each
# needs) come from the data supplied for this project. Every major totals exactly 48 cp.
# ILLUSTRATIVE: sessions_offered for the added subjects is invented, like the rest.
# PREREQUISITES: the rules for these subjects are treated as correct, like the original 12, and are not
# independently verified against the official handbook.

# Subjects that appear only in other majors. (They are stored once, however many majors use them.)
MAJOR_ONLY_SUBJECTS = [
    ("31005", "Machine Learning", 6, "major_other", "Both", "", 0),
    ("31080", "Interactive Media", 6, "major_other", "Both", "", 0),
    ("31241", "Interactive 3D Animation", 6, "major_other", "Autumn", "", 0),
    ("31243", "AI/Analytics Capstone Project B", 6, "major_other", "Both", "", 0),
    ("31245", "Business Process and IT Strategy", 6, "major_other", "Both", "", 0),
    ("31247", "Collaborative Business Processes", 6, "major_other", "Autumn", "", 0),
    ("31250", "Introduction to Data Analytics", 6, "major_other", "Both", "", 0),
    ("31257", "Information System Development Methodologies", 6, "major_other", "Both", "", 0),
    ("31258", "Innovations for Global Relationship Management", 6, "major_other", "Spring", "", 0),
    ("31262", "Game Design Methodologies", 6, "major_other", "Both", "", 0),
    ("31263", "Introduction to Computer Game Development", 6, "major_other", "Autumn", "", 0),
    ("31264", "Computer Graphics", 6, "major_other", "Spring", "", 0),
    ("31266", "Introduction to Information Systems", 6, "major_other", "Both", "", 0),
    ("31275", "Mobile Networking", 6, "major_other", "Autumn", "", 0),
    ("31277", "Routing and Switching Essentials", 6, "major_other", "Both", "", 0),
    ("31748", "Programming on the Internet", 6, "major_other", "Spring", "", 0),
    ("32009", "Advanced Routing Principles", 6, "major_other", "Both", "", 0),
    ("32011", "Multilayer Switched Networks", 6, "major_other", "Both", "", 0),
    ("32146", "Data Visualisation and Visual Analytics", 6, "major_other", "Spring", "", 0),
    ("35005", "Lebesgue Integration and Fourier Analysis", 6, "major_other", "Both", "", 0),
    ("35007", "Mathematics 3", 6, "major_other", "Spring", "", 0),
    ("37161", "Probability and Random Variables", 6, "major_other", "Spring", "", 0),
    ("37233", "Linear Algebra", 6, "major_other", "Spring", "", 0),
    ("37234", "Mathematical Analysis", 6, "major_other", "Autumn", "", 0),
    ("37252", "Regression and Linear Models", 6, "major_other", "Spring", "", 0),
    ("37262", "Mathematical Statistics", 6, "major_other", "Autumn", "", 0),
    ("37373", "Programming for Data Analysis", 6, "major_other", "Autumn", "", 0),
    ("40007", "iOS Innovation Studio", 6, "major_other", "Spring", "", 0),
    ("41019", "Prototyping Physical Interaction", 6, "major_other", "Spring", "", 0),
    ("41020", "Human-centred Design Methods", 6, "major_other", "Autumn", "", 0),
    ("41076", "Methods in Quantum Computing", 6, "major_other", "Spring", "", 0),
    ("41171", "Quantum Computer Architectures", 6, "major_other", "Spring", "", 0),
    ("41173", "Quantum Software and Programming", 6, "major_other", "Spring", "", 0),
    ("41174", "Quantum Algorithms", 6, "major_other", "Both", "", 0),
    ("41180", "Data Analytics in Cybersecurity", 6, "major_other", "Autumn", "", 0),
    ("41181", "Information Security and Management", 6, "major_other", "Spring", "", 0),
    ("41182", "System Security", 6, "major_other", "Autumn", "", 0),
    ("41183", "Privacy Preserving", 6, "major_other", "Spring", "", 0),
    ("41184", "Secure Programming and Penetration Testing", 6, "major_other", "Autumn", "", 0),
    ("41185", "Emerging Topics in Cybersecurity and Privacy", 6, "major_other", "Spring", "", 0),
    ("41191", "Business Intelligence", 6, "major_other", "Both", "", 0),
    ("41801", "Technical Direction for 3D Animation and Graphics Projects", 6, "major_other", "Both", "", 0),
    ("41890", "Applying Network Security", 6, "major_other", "Both", "", 0),
    ("41900", "Cryptography", 6, "major_other", "Spring", "", 0),
    ("41905", "Software Defined Networks", 6, "major_other", "Spring", "", 0),
    ("42028", "Deep Learning and Convolutional Neural Network", 6, "major_other", "Both", "", 0),
    ("42036", "Cybersecurity for Mobile Platforms", 6, "major_other", "Both", "", 0),
    ("42037", "IoT Security", 6, "major_other", "Both", "", 0),
    ("42050", "SAS Predictive Business Analytics", 6, "major_other", "Spring", "", 0),
    ("42891", "Infrastructure for Cloud Computing", 6, "major_other", "Spring", "", 0),
    ("43023", "Emerging Topics in Artificial Intelligence", 6, "major_other", "Autumn", "", 0),
    ("43025", "Introduction to Quantum Computing", 6, "major_other", "Both", "", 0),
    ("43036", "Natural Language Processing", 6, "major_other", "Both", "", 0),
    ("43037", "Network Servers", 6, "major_other", "Spring", "", 0),
    ("48033", "Internet of Things", 6, "major_other", "Both", "", 0),
    ("48436", "Digital Forensics", 6, "major_other", "Both", "", 0),
    ("48730", "Cybersecurity", 6, "major_other", "Autumn", "", 0),
    ("57304", "The Ethics of Data and AI", 6, "major_other", "Spring", "", 0),
    ("68416", "Computational Methods", 6, "major_other", "Spring", "", 0),
    ("68746", "Advanced Quantum Science", 6, "major_other", "Both", "", 0),
]

# (code, name, core cp, options cp)
MAJORS = [
    ("MAJ03519", "Enterprise Software Development", 30, 18),
    ("MAJ10053", "Artificial Intelligence and Data Analytics", 18, 30),
    ("MAJ02080", "Business Information Systems Management", 48, 0),
    ("MAJ02900", "Cybersecurity and Privacy", 42, 6),
    ("MAJ02092", "Interaction Design", 42, 6),
    ("MAJ01156", "Mathematical Analysis", 42, 6),
    ("MAJ03445", "Networking and Cybersecurity", 36, 12),
    ("MAJ02901", "Quantum Computing", 30, 18),
]

# (major code, subject code, role). role is "core" (compulsory) or "option" (chosen from a list).
MAJOR_SUBJECTS = [
    # MAJ03519
    ("MAJ03519", "41025", "core"),
    ("MAJ03519", "31282", "core"),
    ("MAJ03519", "41026", "core"),
    ("MAJ03519", "48433", "core"),
    ("MAJ03519", "41759", "core"),
    ("MAJ03519", "41052", "option"),
    ("MAJ03519", "32113", "option"),
    ("MAJ03519", "31777", "option"),
    ("MAJ03519", "41889", "option"),
    ("MAJ03519", "31927", "option"),
    ("MAJ03519", "41001", "option"),
    ("MAJ03519", "31260", "option"),
    ("MAJ03519", "41113", "option"),
    ("MAJ03519", "41040", "option"),
    # MAJ10053
    ("MAJ10053", "31250", "core"),
    ("MAJ10053", "41040", "core"),
    ("MAJ10053", "41759", "core"),
    ("MAJ10053", "31243", "option"),
    ("MAJ10053", "32146", "option"),
    ("MAJ10053", "42028", "option"),
    ("MAJ10053", "43023", "option"),
    ("MAJ10053", "43025", "option"),
    ("MAJ10053", "31005", "option"),
    ("MAJ10053", "43036", "option"),
    ("MAJ10053", "42050", "option"),
    ("MAJ10053", "57304", "option"),
    # MAJ02080
    ("MAJ02080", "31266", "core"),
    ("MAJ02080", "31257", "core"),
    ("MAJ02080", "31247", "core"),
    ("MAJ02080", "31245", "core"),
    ("MAJ02080", "31258", "core"),
    ("MAJ02080", "32146", "core"),
    ("MAJ02080", "41191", "core"),
    ("MAJ02080", "41759", "core"),
    # MAJ02900
    ("MAJ02900", "48730", "core"),
    ("MAJ02900", "41180", "core"),
    ("MAJ02900", "41900", "core"),
    ("MAJ02900", "41181", "core"),
    ("MAJ02900", "41182", "core"),
    ("MAJ02900", "41183", "core"),
    ("MAJ02900", "41184", "core"),
    ("MAJ02900", "48436", "option"),
    ("MAJ02900", "41185", "option"),
    # MAJ02092
    ("MAJ02092", "31260", "core"),
    ("MAJ02092", "31777", "core"),
    ("MAJ02092", "31080", "core"),
    ("MAJ02092", "41019", "core"),
    ("MAJ02092", "31263", "core"),
    ("MAJ02092", "31264", "core"),
    ("MAJ02092", "41759", "core"),
    ("MAJ02092", "41889", "option"),
    ("MAJ02092", "31262", "option"),
    ("MAJ02092", "41020", "option"),
    ("MAJ02092", "31241", "option"),
    ("MAJ02092", "40007", "option"),
    ("MAJ02092", "31748", "option"),
    ("MAJ02092", "41801", "option"),
    # MAJ01156
    ("MAJ01156", "37233", "core"),
    ("MAJ01156", "37161", "core"),
    ("MAJ01156", "37252", "core"),
    ("MAJ01156", "35007", "core"),
    ("MAJ01156", "37373", "core"),
    ("MAJ01156", "68416", "core"),
    ("MAJ01156", "37234", "core"),
    ("MAJ01156", "35005", "option"),
    ("MAJ01156", "37262", "option"),
    # MAJ03445
    ("MAJ03445", "31277", "core"),
    ("MAJ03445", "31275", "core"),
    ("MAJ03445", "48730", "core"),
    ("MAJ03445", "43037", "core"),
    ("MAJ03445", "42891", "core"),
    ("MAJ03445", "41759", "core"),
    ("MAJ03445", "32009", "option"),
    ("MAJ03445", "41890", "option"),
    ("MAJ03445", "41900", "option"),
    ("MAJ03445", "42036", "option"),
    ("MAJ03445", "48436", "option"),
    ("MAJ03445", "48033", "option"),
    ("MAJ03445", "42037", "option"),
    ("MAJ03445", "32011", "option"),
    ("MAJ03445", "41905", "option"),
    # MAJ02901
    ("MAJ02901", "37233", "core"),
    ("MAJ02901", "43025", "core"),
    ("MAJ02901", "41076", "core"),
    ("MAJ02901", "41173", "core"),
    ("MAJ02901", "41759", "core"),
    ("MAJ02901", "41052", "option"),
    ("MAJ02901", "42028", "option"),
    ("MAJ02901", "31250", "option"),
    ("MAJ02901", "31005", "option"),
    ("MAJ02901", "37262", "option"),
    ("MAJ02901", "37161", "option"),
    ("MAJ02901", "41174", "option"),
    ("MAJ02901", "41171", "option"),
    ("MAJ02901", "68746", "option"),
]

# Prerequisites for the subjects added with the other majors, treated like the original supplied rules.
# (subject code, prerequisite code, alt_group, concurrent). Rows of one subject are ANDed by alt_group; rows that
# share an alt_group are alternatives (OR). concurrent = 1 means the prerequisite may be taken at the same time.
MAJOR_PREREQUISITES = [
    ("42028", "31250", 0, 0),  # Deep Learning <- Introduction to Data Analytics
    ("31005", "31250", 0, 0),  # Machine Learning <- Introduction to Data Analytics AND Programming 2
    ("31005", "48024", 1, 0),
    ("43025", "33230", 0, 0),  # Introduction to Quantum Computing <- Mathematics 2
    ("42050", "31250", 0, 0),  # SAS Predictive Business Analytics <- Introduction to Data Analytics
    # Data Visualisation <- (Intro to Data Analytics OR Intro to Information Systems) AND (Programming 2 OR Intro to AI).
    # Intro to Information Systems is the alternative entry route suggested in the supplied notes; without it this
    # core subject of Business Information Systems could never be taken, because that major does not include 31250.
    ("32146", "31250", 0, 0),
    ("32146", "31266", 0, 0),
    ("32146", "48024", 1, 0),
    ("32146", "41040", 1, 0),
    ("31257", "31269", 0, 0),  # Information System Development Methodologies <- Business Requirements Modelling
    ("31247", "31266", 0, 0),  # Collaborative Business Processes <- Introduction to Information Systems
    ("31258", "31269", 0, 0),  # Innovations for Global Relationship Management <- Business Requirements Modelling
    ("48730", "41092", 0, 0),  # Cybersecurity <- Network Fundamentals AND Web Systems
    ("48730", "31268", 1, 0),
    ("41180", "48730", 0, 0),  # Data Analytics in Cybersecurity <- Cybersecurity
    ("41900", "48730", 0, 0),  # Cryptography <- Cybersecurity
    ("41184", "31251", 0, 0),  # Secure Programming and Penetration Testing <- Data Structures and Algorithms
    ("48436", "48730", 0, 0),  # Digital Forensics <- Cybersecurity
    ("41019", "31260", 0, 0),  # Prototyping Physical Interaction <- Fundamentals of Interaction Design
    ("31264", "31080", 0, 0),  # Computer Graphics <- Interactive Media OR Intro to Computer Game Development
    ("31264", "31263", 0, 0),
    ("31262", "31263", 0, 0),  # Game Design Methodologies <- Intro to Computer Game Development
    ("37233", "33130", 0, 0),  # Linear Algebra <- Mathematics 1
    ("37161", "33130", 0, 1),  # Probability and Random Variables <- Mathematics 1 (may be taken at the same time)
    ("35007", "33230", 0, 0),  # Mathematics 3 <- Mathematics 2
    ("32009", "31277", 0, 0),  # Advanced Routing Principles <- Routing and Switching Essentials (+ 30 cp in the major)
    ("32011", "31277", 0, 0),  # Multilayer Switched Networks <- Routing and Switching Essentials (+ 30 cp in the major)
    ("41905", "31277", 0, 0),  # Software Defined Networks <- Routing and Switching Essentials AND Programming 1
    ("41905", "41039", 1, 0),
    ("41173", "43025", 0, 0),  # Quantum Software and Programming <- Intro to Quantum Computing AND Programming 1
    ("41173", "41039", 1, 0),
    ("41174", "41076", 0, 0),  # Quantum Algorithms <- Methods in Quantum Computing
]

# (subject code, major code, minimum completed credit points within that major)
CREDIT_REQUIREMENTS = [
    ("32009", "MAJ03445", 30),
    ("32011", "MAJ03445", 30),
]

# Leads the app cannot enforce. Shown on the subject, never blocking. The first is a subject that is not in this
# data; the other three belong to the original subjects, whose supplied rules are treated as complete.
PREREQUISITE_NOTES = {
    "31243": "41004, an external subject that is not in this data (so it is not enforced)",
    "41040": "41039 Programming 1 (preliminary; the original supplied data lists no prerequisite, so it is not enforced)",
    "31260": "41039 Programming 1 (preliminary; the original supplied data lists no prerequisite, so it is not enforced)",
    "31777": "31260 Fundamentals of Interaction Design (preliminary; the original supplied data lists no prerequisite, so it is not enforced)",
}