"""Enrolment business logic (grows in later chunks)."""


def session_sort_key(label):
    """Order session labels like 'Autumn 2025' chronologically (Autumn before Spring)."""
    season, year = label.split()
    return int(year), 0 if season == "Autumn" else 1