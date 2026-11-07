"""A timetable as an iCalendar file (RFC 5545), so it can go into Google, Apple or Outlook calendar.

Pure functions: no database and no Flask, so every rule of the format is easy to test. The dates are illustrative like everything else
in the timetable (class times, rooms and due weeks are invented): a session starts on the first Monday on or after a fixed day, and has
13 teaching weeks. The file says so in its description.
"""
import re
from datetime import date, datetime, timedelta, timezone

TEACHING_WEEKS = 13
TZID = "Australia/Sydney"
DAY_INDEX = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4}
START_RULE = {"Autumn": (2, 22), "Spring": (7, 26)}  # a session starts on the first Monday on or after this month and day
PRODID = "-//Enrolment Hub//Timetable//EN"
LABEL = re.compile(r"^(Autumn|Spring) (20\d\d)$")

# Sydney's daylight saving: it starts on the first Sunday of October and ends on the first Sunday of April
VTIMEZONE = [
    "BEGIN:VTIMEZONE", f"TZID:{TZID}",
    "BEGIN:STANDARD", "DTSTART:19700405T030000", "RRULE:FREQ=YEARLY;BYMONTH=4;BYDAY=1SU", "TZNAME:AEST", "TZOFFSETFROM:+1100", "TZOFFSETTO:+1000", "END:STANDARD",
    "BEGIN:DAYLIGHT", "DTSTART:19701004T020000", "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=1SU", "TZNAME:AEDT", "TZOFFSETFROM:+1000", "TZOFFSETTO:+1100", "END:DAYLIGHT",
    "END:VTIMEZONE",
]


def session_start(label):
    """The Monday of week 1 of a session such as 'Autumn 2027'."""
    match = LABEL.match(label)
    if not match:
        raise ValueError(f"not a session: {label!r}")
    month, day = START_RULE[match.group(1)]
    first = date(int(match.group(2)), month, day)
    return first + timedelta(days=(-first.weekday()) % 7)


def escape(text):
    """Escape text for a property value: backslash, semicolon, comma and line breaks (RFC 5545 section 3.3.11)."""
    return str(text).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")


def fold(line):
    """Fold a content line so no physical line is longer than 75 octets (section 3.1), never splitting a multi-byte character.
    Each continuation line starts with one space, which counts towards its 75."""
    lines, current, size = [], "", 0
    for char in line:
        width = len(char.encode("utf-8"))
        if size + width > 75:
            lines.append(current)
            current, size = " " + char, 1 + width
        else:
            current += char
            size += width
    lines.append(current)
    return "\r\n".join(lines)


def slug(label):
    return re.sub(r"[^a-z0-9-]", "", label.lower().replace(" ", "-"))


def stamp(moment):
    return moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def class_event(item, label, now):
    """One weekly class as a repeating event: the same day and time for each of the 13 teaching weeks."""
    day = session_start(label) + timedelta(days=DAY_INDEX[item["day"]])
    start = datetime(day.year, day.month, day.day, item["start_hour"])
    end = start + timedelta(hours=item["duration"])
    return [
        "BEGIN:VEVENT",
        f"UID:class-{item['id']}-{slug(label)}@enrolment-hub",
        f"DTSTAMP:{stamp(now)}",
        f"DTSTART;TZID={TZID}:{start:%Y%m%dT%H%M%S}",
        f"DTEND;TZID={TZID}:{end:%Y%m%dT%H%M%S}",
        f"RRULE:FREQ=WEEKLY;COUNT={TEACHING_WEEKS}",
        f"SUMMARY:{escape(item['subject_code'] + ' ' + item['subject_name'] + ': ' + item['name'])}",
        f"LOCATION:{escape(item['room'])}",
        f"DESCRIPTION:{escape('Class times and rooms are invented for this prototype.')}",
        "END:VEVENT",
    ]


def due_event(task, label, now):
    """An assessment due week as an all-day event on the Friday of that week. Only the week is known, so the description says so."""
    friday = session_start(label) + timedelta(weeks=task["week"] - 1, days=4)
    weight = f" ({task['weight_text']})" if task.get("weight_text") else ""
    return [
        "BEGIN:VEVENT",
        f"UID:due-{task['code']}-{task['index']}-{slug(label)}@enrolment-hub",
        f"DTSTAMP:{stamp(now)}",
        f"DTSTART;VALUE=DATE:{friday:%Y%m%d}",
        f"DTEND;VALUE=DATE:{friday + timedelta(days=1):%Y%m%d}",
        f"SUMMARY:{escape('Due: ' + task['code'] + ' ' + task['name'] + weight)}",
        f"DESCRIPTION:{escape(f'Due in week {task['week']} of {label}. Due weeks are illustrative: the exact day is in your subject outline.')}",
        "TRANSP:TRANSPARENT",
        "END:VEVENT",
    ]


def build_calendar(label, items, due_tasks=(), now=None):
    """The whole .ics text for one session: CRLF line endings, folded lines, one repeating event per class and, if asked, the due weeks."""
    now = now or datetime.now(timezone.utc)
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape('Enrolment Hub: ' + label)}", f"X-WR-TIMEZONE:{TZID}",
        f"X-WR-CALDESC:{escape('Your timetable from Enrolment Hub. Session dates, class times, rooms and due weeks are illustrative.')}",
        *VTIMEZONE,
    ]
    for item in sorted(items, key=lambda i: (DAY_INDEX[i["day"]], i["start_hour"], i["subject_code"], i["id"])):
        lines += class_event(item, label, now)
    for task in due_tasks:
        lines += due_event(task, label, now)
    lines.append("END:VCALENDAR")
    return "".join(fold(line) + "\r\n" for line in lines)
