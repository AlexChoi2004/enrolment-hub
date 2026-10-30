import re

from accounts.seed import DEMO_EMAIL

JANE = "jane.smith@student.uni.edu.au"


def profile_text(client):
    return client.get("/profile").get_data(as_text=True)


def test_anonymous_visitors_are_sent_to_login(client):
    res = client.get("/profile")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]
    assert "next=/profile" in res.headers["Location"]


def test_demo_student_profile_shows_their_details(client, log_in):
    log_in()
    page = profile_text(client)
    assert "John Doe" in page
    assert "DEMO0001" in page
    assert DEMO_EMAIL in page
    assert "Bachelor of Computing Science (Honours) (C09119)" in page
    assert "Enterprise Software Development (MAJ03519)" in page
    assert "Autumn 2025" in page  # when they started
    assert "Year 3" in page
    assert "120 of 192 credit points counted" in page
    assert "96 completed, 24 in progress" in page


def test_demo_profile_mentions_the_reset_command(client, log_in):
    log_in()
    assert "reset-demo" in profile_text(client)


def test_new_student_profile_shows_year_1_and_no_progress(client, register):
    register()
    page = profile_text(client)
    assert "Jane Smith" in page
    assert JANE in page
    assert re.search(r"S\d{7}", page)
    assert "Year 1" in page
    assert "0 of 192 credit points counted" in page
    assert "reset-demo" not in page  # only the shared demo student gets that note


def test_profile_only_ever_shows_the_signed_in_student(client, register):
    register()
    page = profile_text(client)
    assert DEMO_EMAIL not in page and "John Doe" not in page and "DEMO0001" not in page


def test_profile_never_shows_password_data(client, log_in):
    log_in()
    page = profile_text(client)
    assert "scrypt" not in page and "pbkdf2" not in page and "password_hash" not in page
    assert "Johndoe#1" not in page


def test_profile_lists_what_the_app_stores(client, log_in):
    log_in()
    page = profile_text(client)
    assert "What this app stores about you" in page
    assert "salted hash" in page


def test_profile_page_is_not_cacheable(client, log_in):
    log_in()
    assert client.get("/profile").headers["Cache-Control"] == "no-store"


def test_the_email_is_shown_on_the_profile_only(client, log_in):
    log_in()
    assert DEMO_EMAIL.encode() not in client.get("/students/me", follow_redirects=True).data
    assert DEMO_EMAIL.encode() not in client.get("/subjects").data


# --- logging out now lives on the profile page ------------------------------------------------

def test_profile_has_a_log_out_button(client, log_in):
    log_in()
    page = profile_text(client)
    assert 'action="/logout"' in page
    assert ">Log out<" in page
    assert 'name="csrf_token"' in page


def test_log_out_from_the_profile_ends_the_session(client, log_in, csrf):
    log_in()
    res = client.post("/logout", data={"csrf_token": csrf("/profile")})
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/login")
    assert client.get("/profile").status_code == 302  # signed out


def test_no_log_out_button_elsewhere_in_the_nav(client, log_in):
    log_in()
    for path in ["/subjects", "/students/me"]:
        page = client.get(path, follow_redirects=True).get_data(as_text=True)
        assert ">Log out<" not in page


# --- navigation layout ---------------------------------------------------------------------------

def test_main_links_are_on_the_left_and_profile_is_on_the_right(client, log_in):
    log_in()
    page = client.get("/subjects").get_data(as_text=True)
    main = page[page.index('class="nav-main"'):page.index('class="nav-account"')]
    account = page[page.index('class="nav-account"'):page.index("</header>")]
    assert main.index(">Subjects<") < main.index(">Record<")
    assert ">Profile<" in account and ">Profile<" not in main


def test_visitors_see_login_and_create_account_on_the_right(client):
    page = client.get("/login").get_data(as_text=True)
    main = page[page.index('class="nav-main"'):page.index('class="nav-account"')]
    account = page[page.index('class="nav-account"'):page.index("</header>")]
    assert ">Subjects<" not in main and ">Record<" not in main
    assert ">Log in<" in account and ">Create account<" in account


def test_the_current_page_is_marked_in_the_nav(client, log_in):
    log_in()
    subjects = client.get("/subjects").get_data(as_text=True)
    assert re.search(r'href="/subjects"[^>]*aria-current="page"', subjects)
    record = client.get("/students/me", follow_redirects=True).get_data(as_text=True)
    assert re.search(r'href="/students/me"[^>]*aria-current="page"', record)
    assert not re.search(r'href="/subjects"[^>]*aria-current="page"', record)
    profile = profile_text(client)
    assert re.search(r'href="/profile"[^>]*aria-current="page"', profile)