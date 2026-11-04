import re

import pytest

from rag.llm import FakeLLM, LLMError
from shared import db

TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')
GOOD = "Programming 2 needs Programming 1 completed first [1]."
SHOWN = "Programming 2 needs Programming 1 completed first."  # the citation marker is taken out of the displayed text


def token(client, path="/profile"):
    return TOKEN.search(client.get(path).get_data(as_text=True)).group(1)


def html(client, url, **kw):
    return client.get(url, follow_redirects=True, **kw).get_data(as_text=True)


def turn_on(client):
    client.post("/ai/mode", data={"csrf_token": token(client)})


def ask(client, question, hx=False, **extra):
    headers = {"HX-Request": "true"} if hx else {}
    return client.post("/ai/ask", data={"csrf_token": token(client), "question": question, **extra}, headers=headers)


def flag(app, user_id):
    conn = db.connect(app.config["DATABASE"])
    try:
        return conn.execute("SELECT ai_mode FROM users WHERE id = ?", (user_id,)).fetchone()[0]
    finally:
        conn.close()


def usage(app, user_id=1):
    conn = db.connect(app.config["DATABASE"])
    try:
        return conn.execute("SELECT COUNT(*) FROM ai_usage WHERE user_id = ?", (user_id,)).fetchone()[0]
    finally:
        conn.close()


@pytest.fixture()
def model(monkeypatch):
    fake = FakeLLM(GOOD)
    monkeypatch.setattr("rag.llm.get_llm", lambda config: fake)
    return fake


# --- AI mode is off until the student turns it on ------------------------------------------------------------------------------------

def test_ai_mode_is_off_by_default_and_the_box_is_hidden(app, client, log_in):
    log_in()
    assert flag(app, 1) == 0
    for url in ("/planner", "/timetable", "/major/MAJ10053", "/submajor/SMJ10157", "/submajor/electives"):
        assert 'class="ask-panel"' not in html(client, url)
    assert "AI mode: Off" in html(client, "/planner")


def test_nothing_is_sent_to_the_model_while_ai_mode_is_off(client, log_in, model):
    log_in()
    assert ask(client, "What does Programming 2 require?").status_code == 403
    assert model.calls == []


def test_the_switch_needs_a_login_and_a_csrf_token(app, client, log_in):
    assert client.post("/ai/mode", data={}).status_code == 302
    log_in()
    assert client.post("/ai/mode", data={}).status_code == 400
    assert client.post("/ai/mode", data={"csrf_token": "forged"}).status_code == 400
    assert client.get("/ai/mode").status_code == 405 and flag(app, 1) == 0


def test_turning_ai_mode_on_and_off(app, client, log_in):
    log_in()
    turn_on(client)
    assert flag(app, 1) == 1
    page = html(client, "/planner")
    assert "AI mode: On" in page and 'class="ask-panel"' in page
    turn_on(client)
    assert flag(app, 1) == 0 and "AI mode: Off" in html(client, "/planner")


def test_the_switch_only_changes_the_signed_in_students_own_setting(app, client, log_in):
    log_in()
    turn_on(client)
    conn = db.connect(app.config["DATABASE"])
    others = conn.execute("SELECT COUNT(*) FROM users WHERE id <> 1 AND ai_mode = 1").fetchone()[0]
    conn.close()
    assert others == 0


def test_the_switch_returns_to_the_same_page_and_never_to_another_site(client, log_in):
    log_in()
    res = client.post("/ai/mode", data={"csrf_token": token(client), "next": "/timetable"})
    assert res.status_code == 303 and res.headers["Location"].endswith("/timetable")
    res = client.post("/ai/mode", data={"csrf_token": token(client), "next": "https://evil.example/"})
    assert res.status_code == 303 and "evil.example" not in res.headers["Location"]
    res = client.post("/ai/mode", data={"csrf_token": token(client), "next": "//evil.example"})
    assert "evil.example" not in res.headers["Location"]


def test_the_database_only_allows_ai_mode_to_be_zero_or_one(conn):
    with pytest.raises(Exception, match="CHECK"):
        conn.execute("UPDATE users SET ai_mode = 2 WHERE id = 1")


# --- where the question box appears ------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("url", ["/planner", "/timetable", "/major/MAJ10053", "/submajor/SMJ10157", "/submajor/electives"])
def test_with_ai_mode_on_the_box_is_on_the_planner_timetable_and_swap_pages(client, log_in, url):
    log_in()
    turn_on(client)
    page = html(client, url)
    assert 'class="ask-panel"' in page and 'name="question"' in page and 'maxlength="500"' in page
    assert "Not enough context" in page and "can be wrong" in page and "Ask a question" in page


@pytest.mark.parametrize("url", ["/subjects", "/transcript", "/students/me", "/profile"])
def test_the_box_is_not_on_other_pages(client, log_in, url):
    log_in()
    turn_on(client)
    assert 'class="ask-panel"' not in html(client, url)


# --- asking ------------------------------------------------------------------------------------------------------------------------------

def test_a_question_is_answered_with_sources(app, client, log_in, model):
    log_in()
    turn_on(client)
    page = ask(client, "What does Programming 2 require?").get_data(as_text=True)
    assert SHOWN in page and "[1]" not in page and "Sources" in page and "48024 Programming 2" in page and "UTS Handbook (indicative)" in page
    assert "Where this comes from (" in page and "AI-written from the app&#39;s sources and checked" in page.replace("app's", "app&#39;s") and "check the sources" in page
    assert usage(app) == 1


def test_an_htmx_request_gets_just_the_answer_fragment(client, log_in, model):
    log_in()
    turn_on(client)
    fragment = ask(client, "What does Programming 2 require?", hx=True).get_data(as_text=True)
    assert "ask-answer" in fragment and "<html" not in fragment
    assert "<html" in ask(client, "What does Programming 2 require?").get_data(as_text=True)


def test_an_unanswerable_question_says_not_enough_context_and_skips_the_model(client, log_in, model):
    log_in()
    turn_on(client)
    page = ask(client, "What is the capital of France?").get_data(as_text=True)
    assert "Not enough context" in page and model.calls == []


def test_a_model_that_is_down_still_shows_the_sources(client, log_in, monkeypatch):
    log_in()
    turn_on(client)
    monkeypatch.setattr("rag.llm.get_llm", lambda config: FakeLLM(LLMError("The AI model could not be reached (URLError).")))
    res = ask(client, "What does Programming 2 require?")
    page = res.get_data(as_text=True)
    assert res.status_code == 200 and "could not be reached" in page and "48024 Programming 2" in page


def test_with_the_model_switched_off_the_sources_are_shown(client, log_in):
    log_in()
    turn_on(client)  # the tests run with AI_BACKEND=off
    page = ask(client, "What does Programming 2 require?").get_data(as_text=True)
    assert "switched off" in page and "48024 Programming 2" in page


def test_a_wrong_answer_is_never_shown_only_the_sources(client, log_in, monkeypatch):
    log_in()
    turn_on(client)
    monkeypatch.setattr("rag.llm.get_llm", lambda config: FakeLLM("Programming 2 costs 9999 dollars [1]."))
    page = ask(client, "What does Programming 2 require?").get_data(as_text=True)
    assert "9999" not in page and "couldn&#39;t check a written answer" in page and "48024 Programming 2" in page


def test_the_models_text_is_escaped(client, log_in, monkeypatch):
    log_in()
    turn_on(client)
    monkeypatch.setattr("rag.llm.get_llm", lambda config: FakeLLM("<script>alert(1)</script> Programming 2 needs Programming 1 [1]."))
    page = ask(client, "What does Programming 2 require?").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;alert(1)&lt;/script&gt;" in page


def test_the_question_is_escaped_on_the_full_page(client, log_in, model):
    log_in()
    turn_on(client)
    page = ask(client, "<img src=x onerror=alert(1)> Programming 2").get_data(as_text=True)
    assert "<img src=x" not in page and "&lt;img src=x" in page


def test_nothing_about_the_student_is_sent_to_the_model(client, log_in, model):
    log_in()
    turn_on(client)
    ask(client, "What does Programming 2 require?")
    sent = " ".join(model.calls[0]).lower()
    assert "john" not in sent and "student.uni.edu.au" not in sent


def test_the_answer_pages_are_not_cacheable(client, log_in, model):
    log_in()
    turn_on(client)
    assert ask(client, "What does Programming 2 require?").headers["Cache-Control"] == "no-store"


# --- the question is checked ---------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("question", ["", "   ", "\n\t"])
def test_an_empty_question_is_refused(app, client, log_in, model, question):
    log_in()
    turn_on(client)
    res = ask(client, question)
    assert res.status_code == 400 and "Type a question first." in res.get_data(as_text=True)
    assert usage(app) == 0 and model.calls == []


def test_a_question_over_500_characters_is_refused(app, client, log_in, model):
    log_in()
    turn_on(client)
    assert ask(client, "a" * 500).status_code == 200
    res = ask(client, "a" * 501)
    assert res.status_code == 400 and "under 500 characters" in res.get_data(as_text=True)


def test_asking_needs_a_login_and_a_csrf_token(client, log_in, model):
    assert client.post("/ai/ask", data={"question": "hi"}).status_code == 302
    log_in()
    turn_on(client)
    assert client.post("/ai/ask", data={"question": "What does Programming 2 require?"}).status_code == 400
    assert client.post("/ai/ask", data={"csrf_token": "forged", "question": "x"}).status_code == 400
    assert model.calls == []


def test_a_missing_question_field_is_refused(client, log_in, model):
    log_in()
    turn_on(client)
    assert client.post("/ai/ask", data={"csrf_token": token(client)}).status_code == 400


# --- limits -------------------------------------------------------------------------------------------------------------------------------------

def test_the_number_of_questions_per_hour_is_limited(app, client, log_in, model):
    app.config["AI_QUESTIONS_PER_HOUR"] = 3
    log_in()
    turn_on(client)
    assert [ask(client, "What does Programming 2 require?").status_code for _ in range(4)] == [200, 200, 200, 429]
    assert "asked a lot of questions" in ask(client, "What does Programming 2 require?").get_data(as_text=True)
    assert usage(app) == 3  # the refused ones are not counted


def test_questions_from_over_an_hour_ago_do_not_count(app, client, log_in, model):
    app.config["AI_QUESTIONS_PER_HOUR"] = 2
    conn = db.connect(app.config["DATABASE"])
    for _ in range(5):
        conn.execute("INSERT INTO ai_usage (user_id, asked_at) VALUES (1, strftime('%Y-%m-%dT%H:%M:%S', 'now', '-2 hours'))")
    conn.commit()
    conn.close()
    log_in()
    turn_on(client)
    assert ask(client, "What does Programming 2 require?").status_code == 200


def test_the_limit_is_per_student(app, client, log_in, model):
    app.config["AI_QUESTIONS_PER_HOUR"] = 1
    from accounts.service import create_user

    conn = db.connect(app.config["DATABASE"])
    other = create_user(conn, "other.student@student.uni.edu.au", "Str0ng#Pass", "Autumn 2027")["id"]
    conn.execute("INSERT INTO ai_usage (user_id) VALUES (?)", (other,))  # someone else has used their allowance
    conn.commit()
    conn.close()
    log_in()
    turn_on(client)
    assert ask(client, "What does Programming 2 require?").status_code == 200


# --- the help page ---------------------------------------------------------------------------------------------------------------------------------

def test_the_help_page_explains_ai_mode(client):
    page = html(client, "/help")
    assert "AI mode" in page and "off until you turn it on" in page and "Not enough context" in page
    assert "what it looked at" in page and "Explain this swap" in page and "can never enrol, withdraw, plan" in page


# --- questions about the student themselves use the tools ----------------------------------------------------------------------------------

def scripted(monkeypatch, *script):
    from rag.llm import ScriptedLLM

    model = ScriptedLLM(script)
    monkeypatch.setattr("rag.llm.get_llm", lambda config: model)
    return model


def test_a_personal_question_uses_the_tools_and_shows_what_was_looked_at(client, log_in, monkeypatch):
    log_in()
    turn_on(client)
    scripted(monkeypatch, [("get_my_plan", {})], "Your Autumn 2027 session is Heavy because of crunch weeks 8 and 11 [get_my_plan].")
    page = ask(client, "Why is my Autumn heavy?").get_data(as_text=True)
    assert "Heavy because of crunch weeks 8 and 11" in page and "What I looked at" in page
    assert "get_my_plan" in page and "Show what it returned" in page and "can only look things up, never change anything" in page


def test_a_rules_question_uses_the_written_sources_not_the_tools(client, log_in, model):
    log_in()
    turn_on(client)
    page = ask(client, "What does Programming 2 require?").get_data(as_text=True)
    assert "What I looked at" not in page and "Sources" in page and "48024 Programming 2" in page


def test_a_personal_question_the_tools_cannot_answer_falls_back_to_the_sources(client, log_in, monkeypatch):
    log_in()
    turn_on(client)
    scripted(monkeypatch, "I don't know.", GOOD)  # no tool used, so the written sources are tried instead
    page = ask(client, "Tell me what Programming 2 requires for me").get_data(as_text=True)
    assert SHOWN in page and "48024 Programming 2" in page and "What I looked at" not in page


def test_a_bad_agent_answer_shows_what_the_tools_returned(client, log_in, monkeypatch):
    log_in()
    turn_on(client)
    scripted(monkeypatch, [("get_my_plan", {})], "You have 99999 credit points [get_my_plan].")
    page = ask(client, "What is my plan?").get_data(as_text=True)
    assert "99999" not in page.replace("99999 credit", "") and "couldn&#39;t check a written answer against your records" in page
    assert "get_my_plan" in page and "Show what it returned" in page


def test_the_agents_text_is_escaped(client, log_in, monkeypatch):
    log_in()
    turn_on(client)
    scripted(monkeypatch, [("get_my_plan", {})], "<script>alert(1)</script> You are in Autumn 2027 [get_my_plan].")
    page = ask(client, "What is my plan?").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page


def test_the_agent_answer_comes_as_a_fragment_for_the_page_box(client, log_in, monkeypatch):
    log_in()
    turn_on(client)
    scripted(monkeypatch, [("get_my_plan", {})], "You are in Autumn 2027 [get_my_plan].")
    fragment = ask(client, "What is my plan?", hx=True).get_data(as_text=True)
    assert "ask-answered" in fragment and "<html" not in fragment and "What I looked at" in fragment


def test_a_clarifying_question_from_the_model_is_shown(client, log_in, monkeypatch):
    log_in()
    turn_on(client)
    scripted(monkeypatch, "Which major do you want to swap to?")
    assert "Which major do you want to swap to?" in ask(client, "Can I swap?").get_data(as_text=True)


def test_the_tools_only_ever_see_the_signed_in_student(app, client, log_in, monkeypatch):
    log_in()
    turn_on(client)
    scripted(monkeypatch, [("get_my_results", {"user_id": 2})], [("get_my_results", {})],
             "You have passed 96 credit points [get_my_results].")
    page = ask(client, "What are my results?").get_data(as_text=True)
    assert "Unknown argument: user_id" in page and "refused" in page  # the attempt to name another student
    assert "You have passed 96 credit points" in page  # the second, valid call used the signed-in student's own records
