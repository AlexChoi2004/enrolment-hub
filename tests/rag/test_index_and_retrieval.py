import re

import pytest

from advisor.service import (
    GOOD_MAX_EXTRA_CP, THINK_EXTRA_CP, THINK_EXTRA_SESSIONS, THINK_MAJOR_PROGRESS, THINK_MAX_CARRY_SHARE,
)
from degree_planner.service import PLAN_SESSIONS
from enrolment.results import GRADES, PASS_MARK
from enrolment.service import MAX_CP_PER_SESSION
from rag.index import build_index
from rag.retrieve import LIMIT, MAX_TOKENS, MIN_COVERAGE, search, stem, tokens
from rag.rules_text import RULES
from workload.service import CRUNCH_COUNT, CRUNCH_WEIGHT


def chunk(conn, ref):
    return conn.execute("SELECT * FROM rag_chunks WHERE ref = ?", (ref,)).fetchone()


def refs(conn, question):
    return [h["ref"] for h in search(conn, question)["hits"]]


# --- the sources --------------------------------------------------------------------------------------------------------------

def test_there_is_one_source_for_every_subject_major_sub_major_and_rule(conn):
    counts = {r["kind"]: r["n"] for r in conn.execute("SELECT kind, COUNT(*) AS n FROM rag_chunks GROUP BY kind")}
    assert counts == {"subject": 181, "major": 8, "submajor": 8, "rule": len(RULES)} and len(RULES) == 18


def test_every_source_has_a_title_a_source_label_and_a_unique_reference(conn):
    rows = conn.execute("SELECT ref, title, source, body FROM rag_chunks").fetchall()
    assert len({r["ref"] for r in rows}) == len(rows)
    assert all(r["title"] and r["source"] and len(r["body"]) > 40 for r in rows)


def test_rebuilding_the_index_changes_nothing(conn):
    before = [tuple(r) for r in conn.execute("SELECT ref, body FROM rag_chunks ORDER BY ref")]
    assert build_index(conn) == len(before)
    assert [tuple(r) for r in conn.execute("SELECT ref, body FROM rag_chunks ORDER BY ref")] == before
    assert refs(conn, "What does Programming 2 require?")[0] == "subject:48024"  # the search index still works


def test_no_source_contains_anything_about_a_student(conn):
    people = [r[0] for r in conn.execute("SELECT email FROM users")] + [r[0] for r in conn.execute("SELECT student_number FROM users")]
    people += [r[0] for r in conn.execute("SELECT display_name FROM users")]
    bodies = " ".join(r["title"] + " " + r["body"] for r in conn.execute("SELECT title, body FROM rag_chunks")).lower()
    for text in people:
        assert text.lower() not in bodies
    assert "student.uni.edu.au" not in bodies and "johndoe#1" not in bodies


def test_a_subject_source_keeps_its_prerequisite_logic(conn):
    body = chunk(conn, "subject:41181")["body"]
    assert "(31257 Information System Development Methodologies or 31266 Introduction to Information Systems" in body
    assert "; 41039 Programming 1" in body and "every line must be met" in body


def test_credit_point_conditions_are_in_the_source(conn):
    assert "72 credit points completed in your degree" in chunk(conn, "subject:31272")["body"]


def test_indicative_assessments_carry_the_illustrative_caveat(conn):
    c = chunk(conn, "subject:48024")
    assert "UTS Handbook (indicative)" in c["source"] and "due week 4 (illustrative)" in c["body"]
    assert "Assessment load:" in c["body"] and "not a UTS rating" in c["body"]


def test_an_unconfirmed_subject_says_not_enough_context_and_shows_no_tasks(conn):
    c = chunk(conn, "subject:41759")
    assert "Not enough context" in c["body"] and "no confirmed assessment information" in c["source"]
    assert "%" not in c["body"] and "due week" not in c["body"] and "Assessment load" not in c["body"]


def test_the_unconfirmed_student_reported_tasks_never_get_into_a_source(conn):
    body = chunk(conn, "subject:43030")["body"].lower()
    assert "job advertisement" not in body and "portfolio" not in body and "skills audit" not in body
    assert "job advertisement" not in " ".join(r[0] for r in conn.execute("SELECT body FROM rag_chunks")).lower()


def test_historical_assessments_say_so(conn):
    c = chunk(conn, "subject:32009")
    assert "Historical" in c["source"] and "Historical information from 2024" in c["body"] and "may have changed" in c["body"]


def test_sample_electives_say_they_are_invented(conn):
    c = chunk(conn, "subject:SYN101")
    assert "Invented sample subject" in c["source"] and "not a real UTS subject" in c["body"]


def test_unresearched_subjects_say_their_prerequisites_are_unverified(conn):
    assert "Prerequisites have not been verified for this subject." in chunk(conn, "subject:37242")["body"]


def test_a_subject_lists_where_it_counts(conn):
    body = chunk(conn, "subject:41759")["body"]
    assert "Enterprise Software Development major (core)" in body and "Quantum Computing major (core)" in body


def test_a_major_source_has_its_core_and_options(conn):
    body = chunk(conn, "major:MAJ03519")["body"]
    assert "30 credit points of core subjects" in body and "41026 Advanced Software Development" in body and "choose 18 credit points" in body


def test_a_sub_major_source_has_core_options_and_languages(conn):
    assert "Core, all required (6 credit points): 41181" in chunk(conn, "submajor:SMJ10157")["body"]
    lote = chunk(conn, "submajor:SMJ09035")["body"]
    assert "Language program Japanese (CBK90495)" in lote and "Choose exactly one language program" in lote
    assert "have not been loaded" in chunk(conn, "submajor:SMJ10196")["body"]  # the empty stream is stated, not invented


# --- the written rules match what the code does ---------------------------------------------------------------------------------------

def rule(conn, ref):
    return chunk(conn, ref)["body"]


def test_the_session_rules_match_the_code(conn):
    text = rule(conn, "rule:session-load")
    assert MAX_CP_PER_SESSION == 24 and "24 credit points" in text and PLAN_SESSIONS == 10 and "ten sessions" in text


def test_the_grade_bands_match_the_code(conn):
    text = rule(conn, "rule:results-grades")
    assert dict(GRADES) == {"HD": 85, "D": 75, "C": 65, "P": 50} and PASS_MARK == 50
    for expected in ("HD for 85 or more", "D for 75 to 84", "C for 65 to 74", "P for 50 to 64", "FL (fail) below 50"):
        assert expected in text


def test_the_swap_advice_rules_match_the_code(conn):
    text = rule(conn, "rule:swap-advice")
    assert f"{GOOD_MAX_EXTRA_CP} credit points (one subject) or fewer" in text
    assert THINK_EXTRA_SESSIONS == 2 and "two or more extra sessions" in text and f"{THINK_EXTRA_CP} or more credit points" in text
    assert f"{round(THINK_MAJOR_PROGRESS * 100)} percent or more through their major" in text
    assert f"under {round(THINK_MAX_CARRY_SHARE * 100)} percent" in text


def test_the_workload_rules_match_the_code(conn):
    text = rule(conn, "rule:workload")
    assert CRUNCH_COUNT == 4 and f"four or more deadlines or {CRUNCH_WEIGHT} percent of marks" in text


def test_the_degree_structure_adds_up(conn):
    text = rule(conn, "rule:degree-structure")
    assert "192 credit points" in text and "96 credit points of core" in text and "48 credit points for a major" in text


def test_the_rules_say_what_is_simulated(conn):
    assert "simulated demonstration data" in rule(conn, "rule:results-grades")
    assert "illustrative" in rule(conn, "rule:data-sources") and "indicative" in rule(conn, "rule:data-sources")


# --- cleaning a question -------------------------------------------------------------------------------------------------------------

def test_tokens_keep_only_content_words():
    assert tokens("What does Programming 2 require?") == ["programming", "2", "require"]


def test_tokens_drop_stopwords_repeats_and_one_letter_scraps_but_keep_a_lone_digit():
    assert tokens("The the THE a b c programming programming") == ["programming"]
    assert tokens("Programming 2") == ["programming", "2"]
    assert tokens("") == [] and tokens("   ?!  ") == [] and tokens("what is the") == []


def test_tokens_are_limited():
    assert len(tokens(" ".join(f"word{i}" for i in range(50)))) == MAX_TOKENS


def test_tokens_contain_only_letters_and_digits():
    for question in ['"quoted" OR NEAR(a b) AND NOT *', "col:title ^start -minus", "'; DROP TABLE x; --", "<script>alert(1)</script>"]:
        assert all(re.fullmatch(r"[a-z0-9]+", t) for t in tokens(question))


def test_the_stemmer_makes_simple_plurals_match():
    assert stem("subjects") == stem("subject") == "subject"
    assert stem("require") == stem("requires") == stem("required") == "requir"
    assert stem("failed") == stem("failing") == stem("fail") == "fail"
    assert stem("prerequisites") == stem("prerequisite")


# --- finding the right sources ----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("question,expected", [
    ("What does Programming 2 require?", "subject:48024"),
    ("What is 41052?", "subject:41052"),
    ("Tell me about Advanced Algorithms", "subject:41052"),
    ("How many credit points is the degree?", "rule:degree-structure"),
    ("What happens if I fail a subject?", "rule:retakes"),
    ("What are the grades?", "rule:results-grades"),
    ("What is in the Enterprise Software Development major?", "major:MAJ03519"),
    ("Which subjects are in the Information Security sub-major?", "submajor:SMJ10157"),
    ("How is assessment load worked out?", "rule:assessment-load"),
    ("how do I swap majors", "rule:swap-advice"),
    ("What does No result yet do?", "rule:simulator"),
    ("Why can't I register?", "rule:accounts"),
])
def test_a_question_finds_its_source_first(conn, question, expected):
    assert refs(conn, question)[0] == expected


def test_synonyms_find_what_the_sources_call_something_else(conn):
    assert "subject:48024" in refs(conn, "what do I need before Programming 2")
    assert "rule:swap-advice" in refs(conn, "how much does switching cost")


def test_a_language_question_finds_the_language_subjects(conn):
    assert refs(conn, "Japanese language subjects")[0].startswith("subject:972")
    assert refs(conn, "stream CBK92069")[0] == "submajor:SMJ10196"


def test_a_hit_must_contain_most_of_the_questions_words(conn):
    for h in search(conn, "Programming 2 prerequisites")["hits"]:
        assert h["coverage"] >= MIN_COVERAGE


def test_only_a_few_sources_come_back(conn):
    assert len(search(conn, "subject")["hits"]) <= LIMIT


@pytest.mark.parametrize("question", [
    "What is the capital of France?", "tell me about the weather in Sydney", "", "   ", "what is the", "?!?!",
    "'; DROP TABLE subjects; --", "NEAR(a b) OR * AND NOT", "Who won the football?", "zzzz qqqq wwww",
])
def test_a_question_the_sources_cannot_answer_is_not_enough_context(conn, question):
    result = search(conn, question)
    assert result["sufficient"] is False and result["hits"] == []


@pytest.mark.parametrize("question", ['"', "*", "NEAR(", "col:title", "-minus", "^start", "a OR", "AND OR NOT", "title:41039", "(((", "%", "_", "\\", "x" * 5000])
def test_search_operators_typed_by_a_student_never_break_the_search(conn, question):
    result = search(conn, question)  # must not raise
    assert isinstance(result["sufficient"], bool)


def test_a_very_long_question_is_cut_down(conn):
    result = search(conn, "Programming 2 prerequisite " + "word " * 5000)
    assert len(result["tokens"]) <= MAX_TOKENS


def test_searching_never_changes_the_data(conn):
    before = [tuple(r) for r in conn.execute("SELECT * FROM rag_chunks ORDER BY id")]
    search(conn, "'; DELETE FROM rag_chunks; --")
    search(conn, "Programming 2")
    assert [tuple(r) for r in conn.execute("SELECT * FROM rag_chunks ORDER BY id")] == before


def test_the_ai_rules_describe_what_the_ai_can_and_cannot_do(conn):
    text = rule(conn, "rule:ai-mode")
    assert "off until the student turns it on" in text and "ten read-only tools" in text and "can never enrol" in text
    assert "Analyst" in text and "Advisor" in text and "Checker" in text and "the student always makes the decision" in text
    assert refs(conn, "What can the AI do?")[0] == "rule:ai-mode"
    assert "rule:mcp" in refs(conn, "What is the MCP server?")
