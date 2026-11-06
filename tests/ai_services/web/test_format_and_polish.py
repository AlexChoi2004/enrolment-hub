import re

import pytest

from ai_services.web.format import TOOL_LABELS, answer_blocks, tool_label
from ai_services.llm import FakeLLM, ScriptedLLM
from ai_services.tools.registry import TOOLS

TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')


def token(client, path="/profile"):
    return TOKEN.search(client.get(path).get_data(as_text=True)).group(1)


def html(client, url):
    return client.get(url, follow_redirects=True).get_data(as_text=True)


def turn_on(client):
    client.post("/ai/mode", data={"csrf_token": token(client)})


def ask(client, question):
    return client.post("/ai/ask", data={"csrf_token": token(client), "question": question}).get_data(as_text=True)


# --- turning a model's text into tidy blocks ------------------------------------------------------------------------------------------

def test_paragraphs_and_bullet_lists_become_blocks():
    text = "The sub-major has these subjects:\n- 41181 Information Security [1]\n- 41182 System Security [1]\n\nThat is all [2]."
    assert answer_blocks(text) == [
        {"kind": "p", "text": "The sub-major has these subjects:"},
        {"kind": "ul", "items": ["41181 Information Security", "41182 System Security"]},
        {"kind": "p", "text": "That is all."},
    ]


@pytest.mark.parametrize("marker", ["[1]", "[12]", "[get_my_plan]", " [1][2]"])
def test_citation_markers_are_taken_out(marker):
    assert answer_blocks(f"You are in Autumn 2027 {marker}.") == [{"kind": "p", "text": "You are in Autumn 2027."}]


@pytest.mark.parametrize("bullet", ["-", "*", "\u2022"])
def test_the_usual_bullet_characters_make_a_list(bullet):
    assert answer_blocks(f"{bullet} one\n{bullet} two") == [{"kind": "ul", "items": ["one", "two"]}]


def test_empty_and_blank_text_gives_no_blocks():
    assert answer_blocks("") == [] and answer_blocks(None) == [] and answer_blocks("\n\n  \n") == []


def test_html_in_the_text_stays_plain_text_for_the_template_to_escape():
    assert answer_blocks("<b>bold</b> <script>x</script>") == [{"kind": "p", "text": "<b>bold</b> <script>x</script>"}]


def test_a_hyphen_inside_a_sentence_is_not_a_bullet():
    assert answer_blocks("Sub-major structure - supplied from the handbook.") == [{"kind": "p", "text": "Sub-major structure - supplied from the handbook."}]


def test_every_tool_has_a_friendly_name():
    assert set(TOOLS) <= set(TOOL_LABELS) and tool_label("get_my_plan") == "your plan" and tool_label("some_new_tool") == "some new tool"


# --- the answers on the page ------------------------------------------------------------------------------------------------------------------

def test_a_list_answer_is_shown_as_a_list_without_citation_markers(client, log_in, monkeypatch):
    log_in()
    turn_on(client)
    reply = "The sub-major has:\n- 41181 Information Security and Management [1]\n- 48730 Cybersecurity [1]"
    monkeypatch.setattr("ai_services.llm.get_llm", lambda config: FakeLLM(reply))
    page = ask(client, "Which subjects are in the Information Security sub-major?")
    assert "<ul><li>41181 Information Security and Management</li><li>48730 Cybersecurity</li></ul>" in page
    assert "[1]" not in page.split("Where this comes from")[0]


def test_the_sources_are_tucked_away_in_a_collapsed_section(client, log_in, monkeypatch):
    log_in()
    turn_on(client)
    monkeypatch.setattr("ai_services.llm.get_llm", lambda config: FakeLLM("Programming 2 needs Programming 1 completed first [1]."))
    page = ask(client, "What does Programming 2 require?")
    assert '<details class="more">' in page and "<details class=\"more\" open" not in page
    assert page.index("Programming 2 needs Programming 1") < page.index("Where this comes from")


def test_what_the_ai_looked_at_is_named_in_plain_words(client, log_in, monkeypatch):
    log_in()
    turn_on(client)
    monkeypatch.setattr("ai_services.llm.get_llm", lambda config: ScriptedLLM([[("get_my_plan", {}), ("get_my_results", {})], "You are in Autumn 2027 and have passed 96 credit points [get_my_plan][get_my_results]."]))
    page = ask(client, "Where am I up to?")
    assert "What I looked at: your plan, your results" in page and "[get_my_plan]" not in page.split("What I looked at")[0]


def test_a_failed_check_shows_a_short_notice_not_a_wall_of_text(client, log_in, monkeypatch):
    log_in()
    turn_on(client)
    monkeypatch.setattr("ai_services.llm.get_llm", lambda config: FakeLLM("It costs 9999 dollars [1]."))
    page = ask(client, "What does Programming 2 require?")
    assert "ask-unverified" in page and "Most relevant sources (" in page and "9999" not in page


# --- the layout ---------------------------------------------------------------------------------------------------------------------------------

def test_the_subjects_header_has_one_fact_per_line_for_a_new_student(client, log_in):
    log_in()
    client.post("/simulator/reset", data={"csrf_token": token(client), "confirm": "yes", "profile": "fresh"})
    page = html(client, "/subjects")
    assert '<p class="degree-name">Bachelor of Computing Science (Honours)</p>' in page
    assert "<p class=\"dim\">You haven't chosen a major yet · <a" in page and "Choose major</a></p>" in page
    assert "<p class=\"dim\">No sub-major yet · <a" in page and "Choose sub-major or electives</a></p>" in page


def test_the_subjects_header_has_one_fact_per_line_with_a_major_and_sub_major(client, log_in):
    log_in()
    page = html(client, "/subjects")
    assert "<p>Enterprise Software Development major · <a" in page and "Swap major</a></p>" in page
    assert "<p>Innovation and Entrepreneurship sub-major · <a" in page and "Swap sub-major</a></p>" in page


def test_the_planner_has_one_setup_card_with_major_first(client, log_in):
    log_in()
    client.post("/simulator/reset", data={"csrf_token": token(client), "confirm": "yes", "profile": "fresh"})
    page = html(client, "/planner")
    assert page.count('class="card setup-card"') == 1 and "Finish setting up your degree" in page
    assert page.index("Choose major</a>") < page.index("Choose sub-major or electives</a>")
    assert "demo-note" not in page


def test_no_setup_card_when_nothing_is_missing(client, log_in):
    log_in()
    assert "setup-card" not in html(client, "/planner")


def test_the_ai_switch_is_styled_like_the_other_links(client, log_in):
    log_in()
    assert 'class="nav-button"' in html(client, "/planner")


def test_buttons_made_from_links_are_not_underlined(client):
    css = client.get("/static/theme.css").get_data(as_text=True)
    assert ".btn, .button { display: inline-block; text-decoration: none;" in css
    assert "a.btn, a.btn:visited { color: var(--on-accent); }" in css and ".setup-row" in css and ".ask-form" in css


def test_the_choose_major_and_sub_major_prompts_are_the_same_compact_row(client, log_in):
    log_in()
    client.post("/simulator/reset", data={"csrf_token": token(client), "confirm": "yes", "profile": "fresh"})
    page = html(client, "/subjects")
    assert page.count('class="card major-prompt prompt-card"') == 2
    assert "You haven&#39;t chosen a major yet.</strong> Choose one to see its subjects here." in page  # Jinja escapes the apostrophe
    assert "You haven&#39;t chosen a sub-major or general electives yet.</strong> Choose one to see its subjects here." in page
    assert page.index(">Choose major</a>") < page.index(">Choose sub-major or electives</a>")  # the major comes first


def test_both_prompts_share_one_colour_and_layout(client):
    css = client.get("/static/theme.css").get_data(as_text=True)
    assert ".cat-major_prompt, .cat-submajor_prompt { --c: var(--accent); }" in css
    assert ".prompt-card { display: flex; align-items: center; justify-content: space-between;" in css
