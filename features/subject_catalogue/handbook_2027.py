"""The Handbook's 2027 structure of every major and sub-major in this degree, as supplied by the student on 8 November 2026.

This is a copy of what the Handbook pages show (codes, names and credit points), kept as DATA so the app can be checked against it: a test fails if
the app's majors, sub-majors or subject names drift from it. It is not shown to students; the app's own tables are. SMJ10196's page was the 2026
version. Each structure is {"cp", "core": [codes], "choose": [(label, cp, [codes])], "stream": [(code, cp)]}.
"""
SUPPLIED_ON = "2026-11-08"

NAMES = {
    # the degree's core and honours core
    "33130": "Mathematics 1", "37181": "Discrete Mathematics", "41039": "Programming 1", "31265": "Communication for IT Professionals",
    "33230": "Mathematics 2", "31269": "Business Requirements Modelling", "31271": "Database Fundamentals", "48024": "Programming 2",
    "31268": "Web Systems", "41092": "Network Fundamentals", "41078": "Computing Science Studio 1", "41080": "Theory of Computing Science",
    "43030": "Professional Practice in Computing", "31251": "Data Structures and Algorithms", "41079": "Computing Science Studio 2",
    "31272": "Project Management and the Professional", "32144": "Technology Research Preparation", "32931": "Honours Project A", "31482": "Honours Project B",
    # majors and sub-majors
    "31250": "Introduction to Data Analytics", "41040": "Introduction to Artificial Intelligence", "41759": "Capstone", "31243": "AI/Analytics Capstone Project B",
    "32146": "Data Visualisation and Visual Analytics", "42028": "Deep Learning and Convolutional Neural Network", "43023": "Emerging Topics in Artificial Intelligence",
    "43025": "Introduction to Quantum Computing", "31005": "Machine Learning", "43036": "Natural Language Processing", "42050": "SAS Predictive Business Analytics",
    "57304": "The Ethics of Data and AI", "31266": "Introduction to Information Systems", "31257": "Information System Development Methodologies",
    "31247": "Collaborative Business Processes", "31245": "Business Process and IT Strategy", "31258": "Innovations for Global Relationship Management",
    "41191": "Business Intelligence", "48730": "Cybersecurity", "41180": "Data Analytics in Cybersecurity", "41900": "Cryptography",
    "41181": "Information Security and Management", "41182": "System Security", "41183": "Privacy Preserving", "41184": "Secure Programming and Penetration Testing",
    "48436": "Digital Forensics", "41185": "Emerging Topics in Cybersecurity and Privacy", "41025": "Introduction to Software Development",
    "31282": "Systems Testing and Quality Management", "41026": "Advanced Software Development", "48433": "Software Architecture", "41052": "Advanced Algorithms",
    "32113": "Advanced Database", "31777": "Advanced Interaction Design", "41889": "Application Development in the iOS Environment",
    "31927": "Application Development with .NET", "41001": "Cloud Computing and Software as a Service", "31260": "Fundamentals of Interaction Design",
    "41113": "Software Development Studio", "31080": "Interactive Media", "41019": "Prototyping Physical Interaction", "31263": "Introduction to Computer Game Development",
    "31264": "Computer Graphics", "31262": "Game Design Methodologies", "41020": "Human-centred Design Methods", "31241": "Interactive 3D Animation",
    "40007": "iOS Innovation Studio", "31748": "Programming on the Internet", "41801": "Technical Direction for 3D Animation and Graphics Projects",
    "37233": "Linear Algebra", "37161": "Probability and Random Variables", "37252": "Regression and Linear Models", "35007": "Mathematics 3",
    "37373": "Programming for Data Analysis", "68416": "Computational Methods", "37234": "Mathematical Analysis", "35005": "Lebesgue Integration and Fourier Analysis",
    "37262": "Mathematical Statistics", "31277": "Routing and Switching Essentials", "31275": "Mobile Networking", "43037": "Network Servers",
    "42891": "Infrastructure for Cloud Computing", "32009": "Advanced Routing Principles", "41890": "Applying Network Security", "42036": "Cybersecurity for Mobile Platforms",
    "48033": "Internet of Things", "42037": "IoT Security", "32011": "Multilayer Switched Networks", "41905": "Software Defined Networks",
    "41076": "Methods in Quantum Computing", "41173": "Quantum Software and Programming", "41174": "Quantum Algorithms", "41171": "Quantum Computer Architectures",
    "68746": "Advanced Quantum Science", "37242": "Introduction to Optimisation", "37345": "Quantitative Management Practice", "43029": "Introduction to Humanitarian Engineering",
    "99200": "Intercultural Communication", "977917": "In-country Contemporary Society Study", "97901": "International Internship", "41130": "Professional Practice Studio",
    "48080": "Introduction to Innovation", "81529": "Futuring for Innovation with Impact", "81546": "Innovation in Complex Systems", "81547": "Leading Creative Innovation",
    "40005": "Advanced iOS Development", "40006": "iOS industry Studio", "37335": "Differential Equations", "37495": "Statistical Design and Models for Evaluation Studies",
    "37363": "Stochastic Processes and Financial Mathematics", "37336": "Vector Calculus and Partial Differential Equations",
    # the Transdisciplinary Electives stream (CBK92069)
    "95002": "TD: Reframing, remixing, reimagining society", "95003": "TD: Sustainability in an interconnected world",
    "95004": "TD: Technologies reimagined in a complex world", "95005": "TD: Shaping technologies that shape us", "95006": "TD: Envisioning futures worth wanting",
    "95007": "TD: Pathways to societal transitions", "95008": "TD: Transdisciplinary action lab", "95009": "TD: Change-making for social impact",
}
CREDIT_POINTS = {"31482": 12}  # every other subject listed here is 6 cp
TD_STREAM = ("CBK92069", 6, ["95002", "95003", "95004", "95005", "95006", "95007", "95008", "95009"])
ELECTIVES_BLOCK = {"cp": 24, "stream": ("CBK92069", 6), "free": ("CBK92186", 18)}  # the general electives choice: 6 cp from the stream, plus 18 cp of free electives

MAJORS = {
    "MAJ10053": {"cp": 48, "core": ["31250", "41040", "41759"], "choose": [("Options", 30, ["31243", "32146", "42028", "43023", "43025", "31005", "43036", "42050", "57304"])]},
    "MAJ02080": {"cp": 48, "core": ["31266", "31257", "31247", "31245", "31258", "32146", "41191", "41759"], "choose": []},
    "MAJ02900": {"cp": 48, "core": ["48730", "41180", "41900", "41181", "41182", "41183", "41184"], "choose": [("Options", 6, ["48436", "41185"])]},
    "MAJ03519": {"cp": 48, "core": ["41025", "31282", "41026", "48433", "41759"],
                 "choose": [("Options", 18, ["41052", "32113", "31777", "41889", "31927", "41001", "31260", "41113", "41040"])]},
    "MAJ02092": {"cp": 48, "core": ["31260", "31777", "31080", "41019", "31263", "31264", "41759"],
                 "choose": [("Options", 6, ["41889", "31262", "41020", "31241", "40007", "31748", "41801"])]},
    "MAJ01156": {"cp": 48, "core": ["37233", "37161", "37252", "35007", "37373", "68416", "37234"], "choose": [("Options", 6, ["35005", "37262"])]},
    "MAJ03445": {"cp": 48, "core": ["31277", "31275", "48730", "43037", "42891", "41759"],
                 "choose": [("Options", 12, ["32009", "41890", "41900", "42036", "48436", "48033", "42037", "32011", "41905"])]},
    "MAJ02901": {"cp": 48, "core": ["37233", "43025", "41076", "41173", "41759"],
                 "choose": [("Options", 18, ["41052", "42028", "31250", "31005", "37262", "37161", "41174", "41171", "68746"])]},
}
SUBMAJORS = {
    "SMJ10165": {"cp": 24, "core": ["37233", "37242", "37345"], "choose": [("Options", 6, ["68416", "37161"])]},
    "SMJ10196": {"cp": 24, "core": ["43029", "99200"], "choose": [("Options", 6, ["977917", "97901", "41130"])], "stream": [("CBK92069", 6)]},
    "SMJ10157": {"cp": 24, "core": ["41181"], "choose": [("Options", 18, ["48730", "41180", "41185", "41183", "41184", "41182"])]},
    "SMJ10156": {"cp": 24, "core": ["48080", "81529", "81546", "81547"], "choose": []},
    "SMJ10190": {"cp": 24, "core": ["40005", "40006", "41889"], "choose": [("Options", 6, ["31777", "41001", "31260", "41020", "40007"])]},
    "SMJ10167": {"cp": 24, "core": [], "choose": [("Options 1", 6, ["35005", "37262"]), ("Options 2", 18, ["37335", "37242", "37345", "37495", "37363", "37336"])]},
    "SMJ10166": {"cp": 24, "core": ["37161", "37252"], "choose": [("Options", 12, ["37242", "37262", "37373", "37495", "37363"])]},
}
# SMJ09035 (Language other than English): one language program, 24 cp (three 8 cp subjects) from the list for that language
LANGUAGES = {
    "Chinese": ["97116", "97113", "97111", "97101", "97102", "97103", "97104", "97105", "97106", "97109", "97114", "97115", "97112"],
    "French": ["97409", "97407", "97401", "97402", "97403", "97404", "97405", "97406", "97410", "97408"],
    "German": ["97607", "97601", "97602", "97603", "97604", "97606", "97608", "97605"],
    "Italian": ["97801", "97802", "97803", "97804", "97808", "97806", "97807", "97805"],
    "Japanese": ["97207", "97201", "97202", "97203", "97204", "97205", "97206", "97208", "97209", "97210"],
    "Spanish": ["97510", "97507", "97509", "97501", "97502", "97503", "97504", "97505", "97506", "97508"],
}
