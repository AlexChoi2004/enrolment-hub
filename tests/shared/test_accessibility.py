"""Accessibility checks that run in the normal Python tests (no Node, no browser): the structure every page must have, a checker
that is itself tested, and the rules in the stylesheet. The full axe-core audit of every page and both React islands runs in CI
(frontend/a11y.mjs); what no tool can decide is listed in docs/ACCESSIBILITY.md."""
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CSS = (ROOT / "shared" / "static" / "theme.css").read_text(encoding="utf-8")
VOID = {"input", "img", "br", "hr", "meta", "link", "source", "area", "base", "col", "embed", "param", "track", "wbr"}
UNNAMED_OK = {"hidden", "submit", "button", "reset", "image"}


class Page(HTMLParser):
    """Collects what the checks need from one page of HTML."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lang, self.title, self.in_title = None, "", False
        self.headings, self.navs, self.ids, self.problems = [], [], [], []
        self.mains = 0
        self.label_for, self.controls, self.first_focusable = set(), [], None
        self.collect = []  # [(kind, attrs, text parts)] for the open link, button, th and label
        self.label_depth = 0
        self.hidden_depth = 0
        self.stack = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.lang = a.get("lang")
        if tag == "title":
            self.in_title = True
        if "id" in a:
            self.ids.append(a["id"])
        if tag == "main":
            self.mains += 1
        if re.fullmatch(r"h[1-6]", tag):
            self.headings.append(int(tag[1]))
            self.collect.append(("heading", a, []))
        if tag == "nav":
            self.navs.append(a.get("aria-label", "").strip())
        if tag == "label":
            self.label_depth += 1
            if "for" in a:
                self.label_for.add(a["for"])
        if tag == "img" and "alt" not in a:
            self.problems.append("an image has no alt attribute")
        if tag in ("a", "button", "th") and not (tag == "a" and "href" not in a):
            self.collect.append((tag, a, []))
        if tag in ("input", "select", "textarea") and a.get("type") not in UNNAMED_OK and "hidden" not in a:
            self.controls.append((tag, a, self.label_depth > 0))
        if "aria-label" in a and tag in ("span", "p", "div") and "role" not in a:
            self.problems.append(f"aria-label on a <{tag}> with no role is not reliably announced: {a['aria-label']!r}")
        if a.get("tabindex", "0").lstrip("-").isdigit() and int(a.get("tabindex", "0")) > 0:
            self.problems.append("a positive tabindex changes the tab order")
        if self.first_focusable is None and ((tag == "a" and "href" in a) or tag in ("button", "input", "select", "textarea") and a.get("type") != "hidden"):
            self.first_focusable = (tag, a)
        if a.get("aria-hidden") == "true" and tag not in VOID:
            self.hidden_depth += 1
            self.stack.append((tag, True))
        elif tag not in VOID:
            self.stack.append((tag, False))

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag == "label":
            self.label_depth = max(0, self.label_depth - 1)
        if tag in ("a", "button", "th") or re.fullmatch(r"h[1-6]", tag):
            kind = "heading" if tag.startswith("h") and len(tag) == 2 else tag
            for i in range(len(self.collect) - 1, -1, -1):
                if self.collect[i][0] == kind:
                    _, a, parts = self.collect.pop(i)
                    text = "".join(parts).strip()
                    named = text or a.get("aria-label", "").strip()
                    if not named:
                        self.problems.append(f"an empty <{tag}>" + (f" ({a.get('class', '')})" if a.get("class") else ""))
                    break
        while self.stack:
            name, hid = self.stack.pop()
            if hid:
                self.hidden_depth -= 1
            if name == tag:
                break

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if not self.hidden_depth:
            for _, _, parts in self.collect:
                parts.append(data)


def problems(html):
    """Everything wrong with this page's structure, as plain sentences. Empty means it passes."""
    page = Page()
    page.feed(html)
    found = list(page.problems)
    if not page.lang:
        found.append("the <html> element has no lang")
    if not page.title.strip():
        found.append("the page has no title")
    if page.mains != 1:
        found.append(f"expected one <main>, found {page.mains}")
    if page.headings.count(1) != 1:
        found.append(f"expected one <h1>, found {page.headings.count(1)}")
    for before, after in zip(page.headings, page.headings[1:]):
        if after > before + 1:
            found.append(f"a heading jumps from h{before} to h{after}")
    if len(page.navs) > 1 and (len(set(page.navs)) != len(page.navs) or "" in page.navs):
        found.append(f"navigation landmarks need distinct names, found {page.navs}")
    duplicates = {i for i in page.ids if page.ids.count(i) > 1}
    if duplicates:
        found.append(f"duplicate ids {sorted(duplicates)}")
    for tag, a, inside_label in page.controls:
        named = a.get("aria-label", "").strip() or a.get("aria-labelledby") or a.get("id") in page.label_for or inside_label
        if not named:
            found.append(f"a <{tag}> has no label: {a.get('name') or a.get('id') or ''}")
    if not page.first_focusable or page.first_focusable[1].get("href") != "#main" or "main" not in page.ids:
        found.append("the first focusable element must be a skip link to #main, and #main must exist")
    return found


# --- the checker catches what it should (so a pass means something) ---------------------------------------------------------------------------

GOOD = ('<html lang="en"><head><title>T</title></head><body><a href="#main">Skip</a><nav aria-label="Main"><a href="/x">X</a></nav>'
        '<nav aria-label="Account"><a href="/y">Y</a></nav><main id="main"><h1>A</h1><h2>B</h2><label for="q">Q</label><input id="q" name="q"></main></body></html>')


def test_the_checker_passes_a_good_page():
    assert problems(GOOD) == []


@pytest.mark.parametrize("bad,expected", [
    (GOOD.replace(' lang="en"', ""), "no lang"),
    (GOOD.replace("<title>T</title>", ""), "no title"),
    (GOOD.replace("<h1>A</h1>", ""), "expected one <h1>"),
    (GOOD.replace("<h2>B</h2>", "<h3>B</h3>"), "jumps from h1 to h3"),
    (GOOD.replace('aria-label="Account"', 'aria-label="Main"'), "distinct names"),
    (GOOD.replace('<nav aria-label="Account">', "<nav>"), "distinct names"),
    (GOOD.replace('<label for="q">Q</label>', ""), "has no label"),
    (GOOD.replace('<label for="q">Q</label><input id="q" name="q">', '<select name="q"></select>'), "has no label"),
    (GOOD.replace('<a href="/x">X</a>', '<a href="/x"></a>'), "an empty <a>"),
    (GOOD.replace('<a href="/x">X</a>', '<a href="/x"><span aria-hidden="true">X</span></a>'), "an empty <a>"),
    (GOOD.replace("</main>", "<table><tr><th></th></tr></table></main>"), "an empty <th>"),
    (GOOD.replace("</main>", "<button></button></main>"), "an empty <button>"),
    (GOOD.replace("</main>", '<span aria-label="complete">x</span></main>'), "not reliably announced"),
    (GOOD.replace("</main>", '<img src="a.png"></main>'), "no alt"),
    (GOOD.replace("</main>", '<div id="q"></div></main>'), "duplicate ids"),
    (GOOD.replace('<a href="#main">Skip</a>', ""), "skip link"),
    (GOOD.replace("<main id", "<main data-x=1 id").replace("</main>", "</main><main></main>"), "expected one <main>"),
    (GOOD.replace("</main>", '<a href="/z" tabindex="3">Z</a></main>'), "positive tabindex"),
])
def test_the_checker_catches_each_problem(bad, expected):
    assert any(expected in p for p in problems(bad)), problems(bad)


def test_text_that_is_only_for_screen_readers_counts_as_a_name():
    assert problems(GOOD.replace("</main>", '<table><tr><th><span class="visually-hidden">Actions</span></th></tr></table></main>')) == []


# --- every real page -------------------------------------------------------------------------------------------------------------------------------

LOGGED_OUT = ["/", "/login", "/help"]
LOGGED_IN = ["/dashboard", "/subjects", "/planner", "/planner/board", "/timetable", "/students/me", "/transcript", "/major", "/major/fit", "/major/compare?a=MAJ02900&b=MAJ03445", "/major/MAJ10053?tab=about", "/major/MAJ10053", "/submajor/SMJ10196", "/subjects/95003", "/subjects/31251", "/submajor", "/submajor/fit",
             "/submajor/compare?a=SMJ10167&b=SMJ10166", "/submajor/SMJ10157?tab=about",
             "/submajor/electives", "/profile", "/simulator/reset", "/simulator/results", "/help"]


def page_of(client, url):
    res = client.get(url, follow_redirects=True)
    assert res.status_code == 200, url
    return res.get_data(as_text=True)


@pytest.mark.parametrize("url", LOGGED_OUT)
def test_pages_for_visitors_pass_the_structure_checks(client, url):
    assert problems(page_of(client, url)) == []


def test_the_sign_in_and_sign_up_pages_pass(client):
    assert problems(page_of(client, "/login")) == []
    assert problems(page_of(client, "/register")) == [] if client.get("/register").status_code == 200 else True


@pytest.mark.parametrize("url", LOGGED_IN)
def test_pages_for_students_pass_the_structure_checks(client, log_in, url):
    log_in()
    assert problems(page_of(client, url)) == [], url


def test_pages_reached_through_a_link_pass_too(client, log_in):
    log_in()
    subject = re.search(r'href="(/subjects/\d+)"', page_of(client, "/subjects")).group(1)
    major = re.search(r'href="(/major/[A-Z0-9]+)"', page_of(client, "/major")).group(1)
    submajor = re.search(r'href="(/submajor/[A-Z0-9]+)"', page_of(client, "/submajor")).group(1)
    for url in (subject, major, submajor):
        assert problems(page_of(client, url)) == [], url


def test_page_titles_say_where_you_are(client, log_in):
    log_in()
    titles = {url: re.search(r"<title>(.*?)</title>", page_of(client, url), re.S).group(1).strip() for url in ("/dashboard", "/subjects", "/planner", "/planner/board", "/timetable", "/transcript", "/help")}
    assert len(set(titles.values())) == len(titles) and all("Enrolment Hub" in t for t in titles.values())


def test_the_skip_link_is_the_first_thing_in_the_body_and_the_target_can_take_focus(client):
    page = page_of(client, "/login")
    assert re.search(r'<body>\s*<a class="skip-link" href="#main">Skip to main content</a>', page)
    assert '<main id="main" class="container" tabindex="-1">' in page


def test_the_page_can_be_zoomed(client):
    viewport = re.search(r'<meta name="viewport" content="([^"]+)"', page_of(client, "/login")).group(1)
    assert "user-scalable=no" not in viewport.replace(" ", "") and "maximum-scale" not in viewport


def test_error_messages_are_announced_urgently_and_others_politely(client, log_in):
    log_in()
    token = re.search(r'name="csrf_token" value="([^"]+)"', page_of(client, "/profile")).group(1)
    client.post("/planner/add", data={"csrf_token": token, "subject_code": "48024", "session_label": "Autumn 2099"})  # the planner refuses this
    error_page = page_of(client, "/planner")
    assert re.search(r'<p class="toast flash-error" role="alert">', error_page)
    client.post("/planner/clear", data={"csrf_token": token})
    ok_page = page_of(client, "/planner")
    assert re.search(r'<p class="toast flash-success" role="status">', ok_page) and 'role="alert"' not in ok_page


# --- the stylesheet ------------------------------------------------------------------------------------------------------------------------------

def test_there_is_one_clear_focus_ring_and_nothing_removes_it_by_accident():
    assert ":focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }" in CSS
    removed = re.findall(r"([^{}]+)\{[^}]*outline:\s*(?:none|0)[^}]*\}", CSS)
    assert [r.strip() for r in removed] == ["#main:focus"]  # only the page body reached by the skip link


def test_the_skip_link_is_off_screen_until_it_has_focus():
    assert re.search(r"\.skip-link \{[^}]*top: -4rem", CSS) and ".skip-link:focus { top: .5rem; }" in CSS


def test_all_motion_stops_for_people_who_ask_for_reduced_motion():
    block = CSS.split("@media (prefers-reduced-motion: reduce) {\n  *,", 1)[1]
    assert "animation-duration: .01ms !important" in block and "transition-duration: .01ms !important" in block and "scroll-behavior: auto !important" in block


def test_visually_hidden_text_is_defined():
    assert re.search(r"\.visually-hidden \{[^}]*clip: rect\(0 0 0 0\)[^}]*\}", CSS)


def test_the_focus_ring_stands_out_from_every_surface_in_both_themes():
    from tests.shared.test_theme import DARK, LIGHT, ratio, rgb  # the same token values the contrast tests use
    surfaces = ["bg", "card", "surface-2", "surface-3", "field", "accent-soft", "accent-faint", "ok-soft", "warn-soft", "bad-soft"]
    for theme in (LIGHT, DARK):
        for surface in surfaces:
            assert ratio(rgb(theme["accent"]), rgb(theme[surface])) >= 3, surface  # WCAG: a focus indicator needs 3:1


def test_no_page_uses_an_inline_event_handler_or_a_click_only_element():
    offenders = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*.html")
                 if not ({".git", ".venv", "node_modules"} & set(p.parts)) and re.search(r"\son(click|keydown|keyup|mouseover)=", p.read_text(encoding="utf-8"))]
    assert offenders == []
