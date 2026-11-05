"""The checks every AI answer goes through, in one place.

The three AI paths (cited answers from the sources, the tool-using agent for questions about the student, and the swap advisor)
all end the same way: the model's text is checked by plain code BEFORE a student sees it, and if it fails, the student sees the
facts instead of the text. These are the checks they share. Each path adds its own on top (real citations, tools that ran, the
Analyst's verdict), but none of them can be argued with by a prompt, because they are code.
"""
import re

NOT_ENOUGH = "Not enough context: I couldn't find anything about that in the app's rules or subject information."
MAX_ANSWER = 1200  # characters
WINDOW = 6  # a run of this many words copied from the instructions counts as repeating them
LINK = re.compile(r"https?://|www\.", re.I)
NUMBER = re.compile(r"\d+(?:\.\d+)?")
# "I have enrolled you...": the AI can only look things up, so any claim that it did something is wrong
ACTION_CLAIM = re.compile(
    r"\b(i(?: have|'ve)?|we(?: have|'ve)?)\s+(?:just\s+)?(enrolled|added|removed|withdrawn|withdrew|swapped|changed|moved|dropped|updated|saved|"
    r"planned|chose|chosen|confirmed|cancelled|deleted|registered)\b|\byou(?:'ve| have)? been (?:enrolled|added|removed|withdrawn|moved)\b",
    re.I,
)


def clean(text):
    """Drop any reasoning block the model wrote, and tidy whitespace (keeping line breaks, so a list stays a list)."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S | re.I)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text.replace("\r", "")).strip()


def has_link(answer):
    return bool(LINK.search(answer))


def claims_action(answer):
    return bool(ACTION_CLAIM.search(answer))


def repeats_instructions(instructions, answer):
    """True if the answer contains any run of WINDOW consecutive words from the instructions it was given (a leaked prompt)."""
    words = re.findall(r"[a-z0-9']+", instructions.lower())
    text = " " + " ".join(re.findall(r"[a-z0-9']+", answer.lower())) + " "
    return any(" " + " ".join(words[i:i + WINDOW]) + " " in text for i in range(len(words) - WINDOW + 1))


def unsupported_numbers(answer, allowed_text):
    """The numbers in the answer that do not appear in the text it was allowed to use, sorted. Empty means every number is grounded."""
    allowed = set(NUMBER.findall(allowed_text))
    return sorted(n for n in set(NUMBER.findall(answer)) if n not in allowed)
