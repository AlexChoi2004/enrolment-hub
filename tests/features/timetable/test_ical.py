"""The calendar file format, tested without a database or a web server."""
from datetime import date, datetime, timedelta, timezone

import pytest

from features.timetable import ical

NOW = datetime(2026, 11, 6, 3, 0, 0, tzinfo=timezone.utc)
LECTURE = {"id": 188, "subject_code": "41026", "subject_name": "Advanced Software Development", "name": "Lecture", "kind": "lecture",
           "day": "Mon", "start_hour": 14, "duration": 1, "room": "Room C136"}
TUTORIAL = {"id": 90, "subject_code": "31272", "subject_name": "Project Management and the Professional", "name": "Tutorial 1 B", "kind": "tutorial",
            "day": "Wed", "start_hour": 9, "duration": 2, "room": "Room B133"}
TASK = {"code": "31272", "index": 0, "name": "Team Charter", "week": 4, "weight_text": "10%"}


# --- reading a file back (a small parser, so the tests check what a calendar program would see) -------------------------------------------------

def unfold(text):
    assert text.endswith("\r\n") and "\n" not in text.replace("\r\n", "") and "\r" not in text.replace("\r\n", "")  # CRLF line endings, nothing else
    lines = []
    for physical in text.split("\r\n")[:-1]:
        if physical.startswith((" ", "\t")):
            lines[-1] += physical[1:]
        else:
            lines.append(physical)
    return lines


def unescape(value):
    out, i = "", 0
    while i < len(value):
        if value[i] == "\\" and i + 1 < len(value):
            out += "\n" if value[i + 1] in "nN" else value[i + 1]
            i += 2
        else:
            out += value[i]
            i += 1
    return out


def parse_ics(text):
    """The calendar as {'props': [(name, params, value)], 'events': [[(name, params, value)]], 'timezone': [...]}."""
    calendar, stack = {"props": [], "events": [], "timezone": []}, []
    for line in unfold(text):
        name_part, _, value = line.partition(":")
        name, *param_parts = name_part.split(";")
        params = dict(p.split("=", 1) for p in param_parts)
        if name == "BEGIN":
            stack.append(value)
            if value == "VEVENT":
                calendar["events"].append([])
            continue
        if name == "END":
            assert stack.pop() == value
            continue
        target = calendar["events"][-1] if "VEVENT" in stack else calendar["timezone"] if "VTIMEZONE" in stack else calendar["props"]
        target.append((name, params, value))
    assert stack == []
    return calendar


def prop(event, name):
    values = [v for n, _, v in event if n == name]
    assert len(values) == 1, (name, values)
    return values[0]


def params_of(event, name):
    return next(p for n, p, _ in event if n == name)


# --- when a session starts ---------------------------------------------------------------------------------------------------------------------

def test_the_two_sessions_of_2027():
    assert ical.session_start("Autumn 2027") == date(2027, 2, 22) and ical.session_start("Spring 2027") == date(2027, 7, 26)


@pytest.mark.parametrize("year", range(2026, 2036))
def test_a_session_always_starts_on_a_monday_in_the_right_week(year):
    autumn, spring = ical.session_start(f"Autumn {year}"), ical.session_start(f"Spring {year}")
    assert autumn.weekday() == spring.weekday() == 0
    assert date(year, 2, 22) <= autumn <= date(year, 2, 28) and date(year, 7, 26) <= spring <= date(year, 8, 1)


@pytest.mark.parametrize("label", ["Winter 2027", "Autumn 27", "autumn 2027", "", "Autumn 2027; DROP", "Autumn 2027\r\nX:y", "Spring  2027", "2027 Autumn"])
def test_anything_that_is_not_a_session_is_refused(label):
    with pytest.raises(ValueError):
        ical.session_start(label)


# --- escaping and folding -------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("plain", "plain"), ("a,b", "a\\,b"), ("a;b", "a\\;b"), ("a\\b", "a\\\\b"), ("a\nb", "a\\nb"), ("a\r\nb", "a\\nb"), ("a\rb", "a\\nb"),
    ("x\\,;\n", "x\\\\\\,\\;\\n"),
])
def test_text_is_escaped(text, expected):
    assert ical.escape(text) == expected


@pytest.mark.parametrize("text", ["plain", "a,b;c\\d", "line one\nline two", "Café ✓ 😀", "\\\\,,;;\n\n"])
def test_escaping_can_be_undone(text):
    assert unescape(ical.escape(text)) == text.replace("\r", "")


def test_a_short_line_is_not_folded():
    assert ical.fold("SUMMARY:short") == "SUMMARY:short"
    assert ical.fold("x" * 75) == "x" * 75


def test_a_long_line_is_folded_into_lines_of_at_most_75_octets_and_unfolds_to_the_original():
    line = "DESCRIPTION:" + "word " * 60
    folded = ical.fold(line)
    physical = folded.split("\r\n")
    assert len(physical) > 1 and all(len(p.encode("utf-8")) <= 75 for p in physical) and all(p.startswith(" ") for p in physical[1:])
    assert physical[0] + "".join(p[1:] for p in physical[1:]) == line


@pytest.mark.parametrize("char", ["é", "✓", "😀"])
def test_folding_never_splits_a_multibyte_character(char):
    line = "SUMMARY:" + char * 80
    for shift in range(0, 5):  # put the character at every possible offset from the boundary
        folded = ical.fold("X" * shift + line)
        for p in folded.split("\r\n"):
            assert len(p.encode("utf-8")) <= 75
            p.encode("utf-8").decode("utf-8")  # valid UTF-8 on every physical line
        assert "".join(p[1:] if i else p for i, p in enumerate(folded.split("\r\n"))) == "X" * shift + line


# --- the calendar --------------------------------------------------------------------------------------------------------------------------------

def build(items=(LECTURE, TUTORIAL), due=(), label="Autumn 2027"):
    return ical.build_calendar(label, list(items), list(due), now=NOW)


def test_the_file_has_the_required_calendar_properties():
    cal = parse_ics(build())
    props = {n: v for n, _, v in cal["props"]}
    assert props["VERSION"] == "2.0" and props["PRODID"] == "-//Enrolment Hub//Timetable//EN" and props["CALSCALE"] == "GREGORIAN" and props["METHOD"] == "PUBLISH"
    assert props["X-WR-CALNAME"] == "Enrolment Hub: Autumn 2027" and props["X-WR-TIMEZONE"] == "Australia/Sydney"
    assert "illustrative" in unescape(props["X-WR-CALDESC"])


def test_the_file_begins_and_ends_correctly_with_crlf_throughout():
    text = build()
    assert text.startswith("BEGIN:VCALENDAR\r\n") and text.endswith("END:VCALENDAR\r\n") and "\n\n" not in text
    assert text.count("BEGIN:") == text.count("END:")


def test_no_physical_line_is_longer_than_75_octets():
    text = build(items=[{**LECTURE, "subject_name": "A very long subject name, " * 8, "room": "A room with ✓ symbols, " * 6}])
    assert all(len(p.encode("utf-8")) <= 75 for p in text.split("\r\n"))


def test_the_sydney_timezone_is_defined_with_daylight_saving():
    zone = parse_ics(build())["timezone"]
    names = [v for n, _, v in zone if n in ("TZID", "TZNAME")]
    assert names == ["Australia/Sydney", "AEST", "AEDT"]
    rules = [v for n, _, v in zone if n == "RRULE"]
    assert rules == ["FREQ=YEARLY;BYMONTH=4;BYDAY=1SU", "FREQ=YEARLY;BYMONTH=10;BYDAY=1SU"]
    assert [v for n, _, v in zone if n == "TZOFFSETTO"] == ["+1000", "+1100"]


def test_each_class_is_one_weekly_event_for_thirteen_weeks():
    events = parse_ics(build())["events"]
    assert len(events) == 2
    lecture = next(e for e in events if prop(e, "UID").startswith("class-188-"))
    assert prop(lecture, "RRULE") == "FREQ=WEEKLY;COUNT=13" and ical.TEACHING_WEEKS == 13
    assert prop(lecture, "DTSTART") == "20270222T140000" and params_of(lecture, "DTSTART") == {"TZID": "Australia/Sydney"}  # a Monday, 2pm
    assert prop(lecture, "DTEND") == "20270222T150000" and prop(lecture, "LOCATION") == "Room C136"
    assert prop(lecture, "SUMMARY") == "41026 Advanced Software Development: Lecture"


def test_the_day_hour_and_length_of_a_class_are_kept():
    tutorial = next(e for e in parse_ics(build())["events"] if prop(e, "UID").startswith("class-90-"))
    assert prop(tutorial, "DTSTART") == "20270224T090000" and prop(tutorial, "DTEND") == "20270224T110000"  # Wednesday, two hours
    assert date(2027, 2, 24).strftime("%a") == "Wed"


def test_spring_classes_start_in_july():
    assert prop(parse_ics(build(label="Spring 2027"))["events"][0], "DTSTART") == "20270726T140000"


def test_every_event_has_a_stamp_and_a_unique_stable_id():
    events = parse_ics(build(due=[TASK]))["events"]
    assert all(prop(e, "DTSTAMP") == "20261106T030000Z" for e in events)
    uids = [prop(e, "UID") for e in events]
    assert len(uids) == len(set(uids)) == 3 and all(u.endswith("@enrolment-hub") for u in uids)
    later = ical.build_calendar("Autumn 2027", [LECTURE, TUTORIAL], [TASK], now=NOW + timedelta(days=30))
    assert [prop(e, "UID") for e in parse_ics(later)["events"]] == uids  # importing it again updates the same events


def test_the_same_class_in_another_session_is_a_different_event():
    assert prop(parse_ics(build(label="Autumn 2027"))["events"][0], "UID") != prop(parse_ics(build(label="Autumn 2028"))["events"][0], "UID")


def test_events_come_out_in_a_fixed_order():
    assert build(items=[TUTORIAL, LECTURE]) == build(items=[LECTURE, TUTORIAL])
    assert [prop(e, "DTSTART")[:8] for e in parse_ics(build())["events"]] == ["20270222", "20270224"]


def test_awkward_text_survives_a_round_trip():
    nasty = {**LECTURE, "subject_name": "Data; Structures, and \\ Algorithms\nSecond line ✓ 😀", "room": "Room 1, Level 2; Wing\\B"}
    event = parse_ics(build(items=[nasty]))["events"][0]
    assert unescape(prop(event, "SUMMARY")) == "41026 Data; Structures, and \\ Algorithms\nSecond line ✓ 😀: Lecture"
    assert unescape(prop(event, "LOCATION")) == "Room 1, Level 2; Wing\\B"


def test_text_cannot_add_a_line_to_the_file():
    nasty = {**LECTURE, "subject_name": "Evil\r\nBEGIN:VEVENT\r\nSUMMARY:injected", "room": "x\nEND:VCALENDAR"}
    cal = parse_ics(build(items=[nasty]))
    assert len(cal["events"]) == 1 and "injected" in unescape(prop(cal["events"][0], "SUMMARY"))
    assert sum(1 for line in unfold(build(items=[nasty])) if line == "END:VCALENDAR") == 1


# --- assessment due weeks ---------------------------------------------------------------------------------------------------------------------------

def due_event(task=TASK, label="Autumn 2027"):
    return parse_ics(build(items=[], due=[task], label=label))["events"][0]


def test_a_due_week_is_an_all_day_event_on_the_friday_of_that_week():
    event = due_event()
    assert prop(event, "DTSTART") == "20270319" and params_of(event, "DTSTART") == {"VALUE": "DATE"}  # week 4 of Autumn 2027
    assert prop(event, "DTEND") == "20270320" and date(2027, 3, 19).strftime("%a") == "Fri"
    assert prop(event, "TRANSP") == "TRANSPARENT"  # a deadline does not make you busy


@pytest.mark.parametrize("week,friday", [(1, "20270226"), (2, "20270305"), (13, "20270521")])
def test_the_first_and_last_teaching_weeks(week, friday):
    assert prop(due_event({**TASK, "week": week}), "DTSTART") == friday


def test_a_due_event_says_what_is_due_and_that_the_date_is_illustrative():
    event = due_event()
    assert unescape(prop(event, "SUMMARY")) == "Due: 31272 Team Charter (10%)"
    assert "week 4 of Autumn 2027" in unescape(prop(event, "DESCRIPTION")) and "illustrative" in unescape(prop(event, "DESCRIPTION"))
    assert unescape(prop(due_event({**TASK, "weight_text": ""}), "SUMMARY")) == "Due: 31272 Team Charter"


def test_due_events_have_their_own_ids():
    uids = [prop(e, "UID") for e in parse_ics(build(due=[TASK, {**TASK, "index": 1, "name": "Report"}]))["events"]]
    assert len(set(uids)) == 4 and sum(u.startswith("due-") for u in uids) == 2


def test_no_due_tasks_means_only_classes():
    assert all(prop(e, "UID").startswith("class-") for e in parse_ics(build())["events"])


def test_an_empty_session_is_still_a_valid_calendar():
    cal = parse_ics(build(items=[]))
    assert cal["events"] == [] and cal["timezone"]


# --- an independent check: a widely used parser must read the file the same way -------------------------------------------------------------------------

def test_an_independent_parser_reads_the_file_and_the_weekly_repeat_keeps_local_time_across_daylight_saving():
    icalendar = pytest.importorskip("icalendar")
    recurring = pytest.importorskip("recurring_ical_events")
    cal = icalendar.Calendar.from_ical(build(items=[LECTURE, TUTORIAL], due=[TASK]))
    assert str(cal["X-WR-CALNAME"]) == "Enrolment Hub: Autumn 2027" and [str(z["TZID"]) for z in cal.walk("VTIMEZONE")] == ["Australia/Sydney"]
    events = cal.walk("VEVENT")
    assert len(events) == 3 and sum(1 for e in events if str(e["UID"]).startswith("due-")) == 1
    lecture = recurring.of(icalendar.Calendar.from_ical(build(items=[LECTURE]))).between((2027, 1, 1), (2027, 12, 31))
    assert len(lecture) == 13
    starts = [o["DTSTART"].dt for o in lecture]
    assert all(s.hour == 14 and s.weekday() == 0 for s in starts)  # 2pm on every Monday...
    assert starts[0].utcoffset() != starts[-1].utcoffset()  # ...even though the clocks went back on 4 April 2027
