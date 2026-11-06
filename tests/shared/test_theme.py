"""Light and dark themes: every colour is a token, both themes define the same tokens, the text is readable in both
(WCAG contrast), the toggle is on every page, and the logic behind it works."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CSS = (ROOT / "shared" / "static" / "theme.css").read_text(encoding="utf-8")


def block(opening):
    """The text between the braces of the block that starts with `opening`."""
    start = CSS.index(opening) + len(opening)
    depth, i = 1, start
    while depth:
        depth += {"{": 1, "}": -1}.get(CSS[i], 0)
        i += 1
    return CSS[start:i - 1]


LIGHT_TEXT = block(":root {")
DARK_AUTO_TEXT = block(':root:not([data-theme="light"]) {')
DARK_EXPLICIT_TEXT = block(':root[data-theme="dark"] {')


def tokens(text):
    return dict(re.findall(r"--([\w-]+):\s*([^;]+);", text))


LIGHT, DARK = tokens(LIGHT_TEXT), tokens(DARK_EXPLICIT_TEXT)


# --- the tokens ---------------------------------------------------------------------------------------------------------------------------

def test_both_themes_define_the_same_tokens():
    assert set(LIGHT) == set(DARK) and len(LIGHT) > 50


def test_the_dark_theme_for_the_system_setting_and_the_explicit_one_are_identical():
    assert tokens(DARK_AUTO_TEXT) == DARK


def test_the_dark_theme_is_a_soft_dark_not_black():
    r, g, b = (int(DARK["bg"][i:i + 2], 16) for i in (1, 3, 5))
    assert 30 <= (r + g + b) / 3 <= 60 and DARK["bg"] != "#000000" and DARK["text"] != "#ffffff"


def test_the_light_theme_keeps_its_original_palette():
    assert (LIGHT["bg"], LIGHT["card"], LIGHT["text"], LIGHT["accent"]) == ("#f6f7f9", "#ffffff", "#1d2433", "#2457d6")


def test_no_colour_is_written_outside_the_token_blocks():
    rest = CSS.replace(LIGHT_TEXT, "").replace(DARK_AUTO_TEXT, "").replace(DARK_EXPLICIT_TEXT, "")
    rest = re.sub(r"/\*.*?\*/", "", rest, flags=re.S)  # comments may use colour words
    stray = re.findall(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(|\bhwb\(|(?<![-\w])(?:white|black|red|green|blue|gray|grey)(?![-\w])", rest)
    assert stray == []


def test_every_variable_that_is_used_is_defined_somewhere():
    defined = set(re.findall(r"(--[\w-]+)\s*:", CSS))
    used = set(re.findall(r"var\((--[\w-]+)", CSS))
    assert sorted(used - defined) == []


def test_the_page_follows_the_system_setting_by_default_and_the_toggle_overrides_it():
    assert "color-scheme: light dark;" in LIGHT_TEXT and 'color-scheme: light;' in CSS and "color-scheme: dark;" in DARK_EXPLICIT_TEXT
    assert "@media (prefers-color-scheme: dark)" in CSS


def test_form_controls_use_the_tokens():
    assert "input, select, textarea { background: var(--field); color: var(--text);" in CSS


# --- readable in both themes (WCAG 2.x contrast) ----------------------------------------------------------------------------------------------

def rgb(value):
    value = value.strip()
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def luminance(color):
    def channel(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in color)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def mix(color, percent, other):
    """CSS color-mix(in srgb, color percent%, other)."""
    return tuple(round(c * percent / 100 + o * (100 - percent) / 100) for c, o in zip(color, other))


THEMES = {"light": LIGHT, "dark": DARK}
TEXT_PAIRS = [  # (text token, background token): body text needs 4.5:1
    ("text", "bg"), ("text", "card"), ("text", "surface-2"), ("text", "surface-3"), ("text", "field"), ("text", "accent-soft"),
    ("text", "accent-faint"), ("text", "ok-soft"), ("text", "ok-faint"), ("text", "warn-soft"), ("text", "bad-soft"),
    ("muted", "bg"), ("muted", "card"), ("muted", "surface-2"), ("muted", "surface-3"), ("muted", "field"), ("muted", "ok-faint"), ("muted", "accent-faint"),
    ("accent", "bg"), ("accent", "card"), ("accent", "surface-2"), ("accent", "accent-soft"), ("accent", "accent-faint"), ("accent", "warn-soft"),
    ("on-accent", "accent"), ("on-ok", "ok"), ("on-bad", "bad"), ("on-grey", "grey"),
    ("ok", "bg"), ("ok", "card"), ("ok", "ok-soft"), ("warn", "bg"), ("warn", "card"), ("warn", "warn-soft"),
    ("bad", "bg"), ("bad", "card"), ("bad", "bad-soft"), ("bad", "warn-soft"),
    ("ok-text", "ok-soft"), ("warn-text", "warn-soft"), ("bad-text", "bad-soft"),
]


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("fg,bg", TEXT_PAIRS)
def test_text_is_readable(theme, fg, bg):
    colors = THEMES[theme]
    assert ratio(rgb(colors[fg]), rgb(colors[bg])) >= 4.5, (theme, fg, bg, round(ratio(rgb(colors[fg]), rgb(colors[bg])), 2))


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("scale", ["scale-1", "scale-2", "scale-3", "scale-4", "scale-5", "scale-teal"])
def test_text_is_readable_on_every_load_and_workload_colour(theme, scale):
    colors = THEMES[theme]
    assert ratio(rgb(colors["text"]), rgb(colors[scale])) >= 4.5


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("category", ["accent", "purple", "teal", "orange", "grey", "violet", "lilac"])
def test_category_badges_are_readable(theme, category):
    colors = THEMES[theme]
    tint = mix(rgb(colors[category]), 12, rgb(colors["card"]))  # .badge.category: a 12% tint of its colour...
    text = mix(rgb(colors[category]), 72, rgb(colors["text"]))  # ...with the colour mixed 72% into the normal text colour
    assert ratio(text, tint) >= 4.5, (theme, category, round(ratio(text, tint), 2))
    assert "color: color-mix(in srgb, var(--c) 72%, var(--text));" in CSS


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("n", range(8))
def test_timetable_blocks_are_readable_and_their_edges_stand_out(theme, n):
    colors = THEMES[theme]
    tint = mix(rgb(colors[f"tt{n}"]), 16, rgb(colors["card"]))  # .tt-c#: the block is a 16% tint of its edge colour
    assert ratio(rgb(colors["text"]), tint) >= 4.5
    assert ratio(rgb(colors[f"tt{n}"]), rgb(colors["card"])) >= 3  # a non-text edge needs 3:1


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("token", ["ok-strong", "orange", "bad-strong", "teal", "grey", "violet", "lilac", "purple"])
def test_coloured_edges_stand_out_from_the_card(theme, token):
    colors = THEMES[theme]
    assert ratio(rgb(colors[token]), rgb(colors["card"])) >= 3


@pytest.mark.parametrize("theme", THEMES)
def test_cards_stand_out_from_the_page(theme):
    colors = THEMES[theme]
    assert colors["card"] != colors["bg"] and ratio(rgb(colors["border"]), rgb(colors["card"])) >= 1.15


def test_the_contrast_maths_is_right():
    assert round(ratio((255, 255, 255), (0, 0, 0)), 1) == 21.0 and round(ratio((119, 119, 119), (255, 255, 255)), 2) == 4.48
    assert mix((0, 0, 0), 50, (255, 255, 255)) == (128, 128, 128)


# --- the toggle is wired up everywhere ----------------------------------------------------------------------------------------------------------

def test_every_page_loads_the_theme_script_in_the_head_without_inline_code(client, log_in):
    log_in()
    for url in ("/login", "/help", "/subjects", "/planner", "/transcript"):
        page = client.get(url, follow_redirects=True).get_data(as_text=True)
        head = page.split("</head>", 1)[0]
        assert '<meta name="color-scheme" content="light dark">' in head
        scripts = re.findall(r"<script[^>]*>", head)
        theme_tag = [s for s in scripts if "theme.js" in s][0]
        assert "defer" not in theme_tag and "async" not in theme_tag  # it must run before the page paints
        assert all("src=" in s for s in scripts)  # no inline scripts: the content security policy forbids them


def test_the_toggle_is_in_the_navigation_for_everyone_and_hidden_until_the_script_runs(client, log_in):
    for logged_in in (False, True):
        if logged_in:
            log_in()
        page = client.get("/help").get_data(as_text=True)
        assert '<button type="button" id="theme-toggle" class="nav-button" aria-pressed="false" hidden>Dark mode</button>' in page


def test_the_script_is_served_and_the_policy_still_blocks_inline_scripts(client):
    res = client.get("/static/theme.js")
    assert res.status_code == 200 and b"prefers-color-scheme" in res.data and b"data-theme" in res.data
    csp = client.get("/login").headers["Content-Security-Policy"]
    assert "script-src 'self'" in csp and "unsafe-inline" not in csp


def test_no_template_sets_a_colour_inline():
    offenders = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*.html")
                 if not ({".git", ".venv", "node_modules"} & set(p.parts))
                 and re.search(r'style="[^"]*(color|background|border)[^"]*"', p.read_text(encoding="utf-8"))]
    assert offenders == []


def test_the_help_page_explains_dark_mode(client):
    page = client.get("/help").get_data(as_text=True)
    assert "Can I use dark mode?" in page and "follows your device or browser setting" in page


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is not installed")
def test_the_toggle_logic_passes_its_node_tests():
    done = subprocess.run(["node", "--test", "tests/js/theme.test.mjs"], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stdout[-1500:]
