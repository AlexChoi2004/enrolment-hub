import json

import pytest

from ai_services.ai_mode.agent import SYSTEM as AGENT_SYSTEM, check_agent_answer
from ai_services.checks import (
    ACTION_CLAIM, MAX_ANSWER, NOT_ENOUGH, WINDOW, claims_action, clean, has_link, repeats_instructions, unsupported_numbers,
)
from ai_services.multi_agent.swap_agents import SYSTEM as ADVISOR_SYSTEM, check as check_advice
from ai_services.rag.answer import SYSTEM as RAG_SYSTEM, check_answer


# --- each shared check on its own --------------------------------------------------------------------------------------------------------

def test_the_shared_constants():
    assert MAX_ANSWER == 1200 and WINDOW == 6 and NOT_ENOUGH.startswith("Not enough context")


@pytest.mark.parametrize("text", ["see https://evil.example", "http://x.example/a", "visit www.evil.example", "HTTPS://LOUD.EXAMPLE"])
def test_links_are_found(text):
    assert has_link(text)


@pytest.mark.parametrize("text", ["no link here", "the www of things", "https is a protocol", "a.b.c"])
def test_ordinary_text_has_no_link(text):
    assert not has_link(text)


@pytest.mark.parametrize("text", ["I have enrolled you in it", "I've moved it to Spring", "we have swapped your major", "You've been withdrawn",
                                  "I just saved the plan", "You have been enrolled in Programming 2"])
def test_claims_of_an_action_are_found(text):
    assert claims_action(text) and ACTION_CLAIM.search(text)


@pytest.mark.parametrize("text", ["You can enrol in it on the Subjects page", "The subject was moved to Spring by the planner suggestion", "Enrolled subjects count",
                                  "You are enrolled in four subjects"])
def test_describing_the_facts_is_not_a_claim_of_an_action(text):
    assert not claims_action(text)


def test_repeating_the_instructions_is_found_for_any_run_of_words():
    instructions = "Never invent numbers, subject codes, dates or links. Use only what the sources say."
    assert repeats_instructions(instructions, "Sure: never invent numbers, subject codes, dates or links okay")
    assert repeats_instructions(instructions, "NEVER   INVENT numbers subject-codes dates OR links")  # case, spacing and punctuation do not hide it
    assert not repeats_instructions(instructions, "You should not make up numbers or codes here")
    assert not repeats_instructions(instructions, "never invent numbers subject")  # fewer than WINDOW words in a row


def test_numbers_in_the_answer_must_come_from_the_allowed_text():
    assert unsupported_numbers("It is 6 credit points and 99 dollars", "6 credit points") == ["99"]
    assert unsupported_numbers("2027 and 3.5", "Autumn 2027 and 3.5 sessions") == []
    assert unsupported_numbers("1, 2 and 10", "1 2") == ["10"]  # "10" is not "1"
    assert unsupported_numbers("no numbers", "") == []


def test_clean_drops_reasoning_and_keeps_lists():
    assert clean("<think>x 99</think>- a\r\n- b\n\n\n\nc") == "- a\n- b\n\nc"


# --- the three AI paths reject the same bad text for the same reasons ------------------------------------------------------------------------

HITS = [{"title": "T", "body": "Programming 2 needs Programming 1. It is worth 6 credit points."}]
FACTS = {"label": "Think carefully", "lost_cp": 36, "extra_cp": 6}


def rag(answer):
    return check_answer(answer + " [1]", HITS, "What does Programming 2 need?")


def agent(answer):
    return check_agent_answer(answer + " [get_my_plan]", {"get_my_plan"}, '{"credit points": 6}', "What is my plan?")


def advisor(answer):
    return check_advice("Think carefully. " + answer + " The decision is yours.", FACTS)


@pytest.mark.parametrize("path", [rag, agent, advisor], ids=["rag", "agent", "advisor"])
class TestEveryPathUsesTheSharedChecks:
    def test_a_link_is_rejected(self, path):
        assert any("web link" in p for p in path("See https://evil.example"))

    def test_an_invented_number_is_rejected(self, path):
        assert any("99999" in p for p in path("It costs 99999 credit points"))

    def test_a_clean_answer_has_no_problem_about_links_or_numbers(self, path):
        problems = path("It is worth 6 credit points")
        assert not any("link" in p or "numbers" in p for p in problems)


@pytest.mark.parametrize("path,system", [(rag, RAG_SYSTEM), (agent, AGENT_SYSTEM), (advisor, ADVISOR_SYSTEM)], ids=["rag", "agent", "advisor"])
def test_every_path_rejects_a_leaked_prompt(path, system):
    leaked = " ".join(system.split()[3:3 + WINDOW + 2])
    assert any("repeated the instructions" in p for p in path(leaked))


@pytest.mark.parametrize("path", [agent, advisor], ids=["agent", "advisor"])
def test_the_paths_that_can_only_look_things_up_reject_a_claim_of_an_action(path):
    assert any("claimed an action" in p for p in path("I have enrolled you in Programming 2"))


def test_an_answer_over_the_length_limit_is_rejected_by_every_path():
    long = "word " * (MAX_ANSWER // 4)
    for path in (rag, agent, advisor):
        assert any("too long" in p for p in path(long))


def test_each_path_still_has_its_own_extra_check():
    assert any("cited no source" in p for p in check_answer("no citation", HITS, "q"))
    assert any("did not name a tool" in p for p in check_agent_answer("no tool", {"get_my_plan"}, "{}", "q"))
    assert any("did not begin with the Analyst's verdict" in p for p in check_advice("Good to switch. The decision is yours.", FACTS))
    assert json.dumps(FACTS)  # the advisor's numbers come from the facts it was given
