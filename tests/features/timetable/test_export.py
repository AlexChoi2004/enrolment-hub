import re

import pytest

from features.timetable import service
from shared import db
from tests.features.timetable.test_ical import parse_ics, prop, unescape

TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')


def token(client):
    return TOKEN.search(client.get("/profile").get_data(as_text=True)).group(1)


def export(client, query=""):
    return client.get("/timetable/export.ics" + query)


def events_of(res):
    return parse_ics(res.get_data(as_text=True))["events"]


def reset_to(client, key):
    client.post("/simulator/reset", data={"csrf_token": token(client), "confirm": "yes", "profile": key})


# --- who can download, and what comes back ----------------------------------------------------------------------------------------------------------

def test_it_needs_a_login(client):
    assert client.get("/timetable/export.ics").status_code == 302


def test_the_answer_is_a_downloadable_calendar_that_is_never_cached(client, log_in):
    log_in()
    res = export(client)
    assert res.status_code == 200
    assert res.headers["Content-Type"] == "text/calendar; charset=utf-8"
    assert res.headers["Content-Disposition"] == 'attachment; filename="enrolment-hub-timetable-autumn-2027.ics"'
    assert res.headers["Cache-Control"] == "no-store" and res.headers["X-Content-Type-Options"] == "nosniff"


def test_it_only_answers_get(client, log_in):
    log_in()
    for method in (client.post, client.put, client.delete, client.patch):
        assert method("/timetable/export.ics").status_code == 405


def test_it_changes_nothing(app, client, log_in):
    log_in()
    conn = db.connect(app.config["DATABASE"])
    tables = ("users", "enrolments", "planned_subjects", "class_choices")
    before = [sorted(tuple(r) for r in conn.execute(f"SELECT * FROM {t}")) for t in tables]  # noqa: S608
    export(client)
    export(client, "?due=1&session=Spring+2027")
    assert before == [sorted(tuple(r) for r in conn.execute(f"SELECT * FROM {t}")) for t in tables]  # noqa: S608
    conn.close()


# --- what is in the file -------------------------------------------------------------------------------------------------------------------------------

def test_every_class_on_the_timetable_is_in_the_file_and_nothing_else(app, client, log_in):
    log_in()
    conn = db.connect(app.config["DATABASE"])
    timetable = service.get_timetable(conn, 1, "Autumn 2027")
    expected = sorted((i["subject_code"], i["name"], i["room"]) for col in timetable["columns"] for i in col["items"])
    got = sorted((unescape(prop(e, "SUMMARY")).split(" ", 1)[0], unescape(prop(e, "SUMMARY")).rsplit(": ", 1)[1], unescape(prop(e, "LOCATION"))) for e in events_of(export(client)))
    assert got == expected and len(expected) >= 4
    conn.close()


def test_only_subjects_the_student_is_enrolled_in_appear(app, client, log_in):
    log_in()
    conn = db.connect(app.config["DATABASE"])
    enrolled = {r[0] for r in conn.execute("SELECT subject_code FROM enrolments WHERE user_id = 1 AND status = 'enrolled' AND session_label = 'Autumn 2027'")}
    codes = {unescape(prop(e, "SUMMARY")).split(" ", 1)[0] for e in events_of(export(client))}
    assert codes and codes <= enrolled
    conn.close()


def test_a_class_the_student_chooses_appears_with_its_room_and_time(app, client, log_in):
    log_in()
    conn = db.connect(app.config["DATABASE"])
    card = next(c for c in service.get_timetable(conn, 1, "Autumn 2027")["subjects"] if c["components"])
    component = card["components"][0]
    option = next(o for o in component["options"] if not o["clash"])
    client.post("/timetable/choose", data={"csrf_token": token(client), "session": "Autumn 2027", "subject_code": card["code"], "class_id": option["id"]})
    events = events_of(export(client))
    chosen = [e for e in events if prop(e, "UID").startswith(f"class-{option['id']}-")]
    assert len(chosen) == 1 and unescape(prop(chosen[0], "LOCATION")) == option["room"]
    day = {"Mon": "20270222", "Tue": "20270223", "Wed": "20270224", "Thu": "20270225", "Fri": "20270226"}[option["when"][:3]]
    assert prop(chosen[0], "DTSTART")[:8] == day and prop(chosen[0], "DTSTART")[9:11] == option["when"][4:6]
    conn.close()


def test_due_weeks_are_only_included_when_asked_for(app, client, log_in):
    log_in()
    plain = events_of(export(client))
    assert all(prop(e, "UID").startswith("class-") for e in plain)
    with_due = events_of(export(client, "?due=1"))
    due = [e for e in with_due if prop(e, "UID").startswith("due-")]
    conn = db.connect(app.config["DATABASE"])
    expected = service.due_tasks(conn, service.get_timetable(conn, 1, "Autumn 2027")["subjects"])
    assert len(due) == len(expected) > 0 and len(with_due) == len(plain) + len(due)
    assert all(unescape(prop(e, "SUMMARY")).startswith("Due: ") and "illustrative" in unescape(prop(e, "DESCRIPTION")) for e in due)
    conn.close()


def test_exam_period_tasks_are_not_given_a_made_up_date(app, client, log_in):
    log_in()
    conn = db.connect(app.config["DATABASE"])
    tasks = service.due_tasks(conn, service.get_timetable(conn, 1, "Autumn 2027")["subjects"])
    assert all(2 <= t["week"] <= 13 for t in tasks)
    conn.close()


@pytest.mark.parametrize("value", ["0", "true", "yes", "", "2", "1; DROP TABLE users"])
def test_only_due_equals_1_switches_on_due_weeks(client, log_in, value):
    log_in()
    assert all(prop(e, "UID").startswith("class-") for e in events_of(export(client, f"?due={value}")))


# --- which session ------------------------------------------------------------------------------------------------------------------------------------

def test_another_open_session_can_be_exported(client, log_in):
    log_in()
    res = export(client, "?session=Spring+2027")
    assert res.status_code in (200, 303)
    if res.status_code == 200:
        assert 'filename="enrolment-hub-timetable-spring-2027.ics"' in res.headers["Content-Disposition"]
        assert 'X-WR-CALNAME:Enrolment Hub: Spring 2027' in res.get_data(as_text=True)


@pytest.mark.parametrize("session", ["Autumn 2099", "../../etc/passwd", '"><script>x</script>', "Autumn 2027\r\nSet-Cookie: x=1", "A" * 500, "Winter 2027", "Autumn+2027; rm -rf"])
def test_a_bad_session_falls_back_to_the_current_one_and_is_never_echoed(client, log_in, session):
    log_in()
    res = client.get("/timetable/export.ics", query_string={"session": session})
    assert res.status_code == 200 and 'filename="enrolment-hub-timetable-autumn-2027.ics"' == res.headers["Content-Disposition"].split("; ", 1)[1]
    body = res.get_data(as_text=True)
    assert session not in body and "Set-Cookie" not in res.headers.get("Content-Disposition", "") and "X-WR-CALNAME:Enrolment Hub: Autumn 2027" in body
    assert re.fullmatch(r'attachment; filename="enrolment-hub-timetable-[a-z0-9-]+\.ics"', res.headers["Content-Disposition"])


# --- nothing to export, and other students --------------------------------------------------------------------------------------------------------------

def test_a_student_with_no_classes_is_sent_back_with_a_message_not_an_empty_file(client, log_in):
    log_in()
    reset_to(client, "fresh")
    res = export(client)
    assert res.status_code == 303 and res.headers["Location"].endswith("/timetable?session=Autumn+2027")
    page = client.get(res.headers["Location"]).get_data(as_text=True)
    assert "You have no classes in Autumn 2027 to add to a calendar yet" in page and "Nothing to add yet" in page and "Download calendar" not in page


def test_a_new_student_never_gets_the_demo_students_classes(client, register):
    register()
    assert export(client).status_code == 303


# --- the page ---------------------------------------------------------------------------------------------------------------------------------------------------

def test_the_timetable_page_offers_the_download_with_a_labelled_option(client, log_in):
    log_in()
    page = client.get("/timetable").get_data(as_text=True)
    assert '<form method="get" action="/timetable/export.ics" class="calendar-form">' in page and '<input type="hidden" name="session" value="Autumn 2027">' in page
    assert '<label class="calendar-option"><input type="checkbox" name="due" value="1"> Include assessment due weeks</label>' in page
    assert "Download calendar (.ics)" in page and "illustrative" in page


def test_the_download_the_form_makes_is_the_one_the_server_answers(client, log_in):
    log_in()
    res = client.get("/timetable/export.ics?session=Autumn+2027&due=1")
    assert res.status_code == 200 and any(prop(e, "UID").startswith("due-") for e in events_of(res))
