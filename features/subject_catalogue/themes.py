"""Focus areas, worked out from subject names.

A program's description says what it is about; to say how two programs differ in focus without guessing, each subject name is matched to a few
themes, and a program's focus areas are the themes that run through several of its subjects. Anyone can check the result: every focus area
lists the subjects behind it.
"""
import re

THEMES = (
    ("Artificial intelligence and machine learning", r"Artificial Intelligence|Machine Learning|Neural|Computational Intelligence|Natural Language|Deep Learning"),
    ("Data analysis and visualisation", r"Data Analytics|Data Visuali|Visual Analytics|Business Intelligence|Predictive|Programming for Data|Analytics"),
    ("Statistics and probability", r"Statist|Probability|Regression|Stochastic"),
    ("Mathematics", r"Algebra|Calculus|Real Analysis|Complex Analysis|Integration|Differential|Optimis|Mathematical|Computational Physics"),
    ("Cybersecurity and privacy", r"Security|Cybersecurity|Cryptograph|Privacy|Forensics|Penetration"),
    ("Networking and infrastructure", r"Network|Routing|Switch|Internet of Things|IoT|Infrastructure|Cloud Computing"),
    ("Software development", r"Software|Application Development|Programming|Studio|Systems Testing|\.NET|iOS Development|Advanced Algorithms"),
    ("Design and user experience", r"Design|Interaction|Interactive|Human-centred|Prototyping"),
    ("Games, graphics and animation", r"Game|Graphics|Animation|3D|Interactive Media"),
    ("Quantum computing", r"Quantum"),
    ("Business and information systems", r"Business|Information System|Enterprise|Management Practice|Relationship Management"),
    ("Innovation and entrepreneurship", r"Innovation|Futuring|Creative|Entrepreneur"),
    ("Global and professional practice", r"Intercultural|Internship|Humanitarian|Professional Practice|In-country"),
)
COMPILED = tuple((label, re.compile(pattern, re.I)) for label, pattern in THEMES)
MIN_SUBJECTS = 2  # a theme needs at least this many subjects to count as a focus area
MAX_AREAS = 5


def themes_of(subject_name):
    """The themes a subject belongs to (a subject can belong to more than one)."""
    return [label for label, pattern in COMPILED if pattern.search(subject_name)]


def focus_areas(subject_names):
    """[{'label', 'subjects': [names]}] for the themes that run through several subjects, the strongest first (at most five).

    A program with very few subjects that matches no theme twice gets its single strongest theme instead, so a short program is never blank."""
    found = {}
    for name in subject_names:
        for label in themes_of(name):
            found.setdefault(label, []).append(name)
    ranked = sorted(found.items(), key=lambda item: (-len(item[1]), item[0]))
    strong = [(label, names) for label, names in ranked if len(names) >= MIN_SUBJECTS] or ranked[:1]
    return [{"label": label, "subjects": names} for label, names in strong[:MAX_AREAS]]
