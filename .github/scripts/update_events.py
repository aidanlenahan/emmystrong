#!/usr/bin/env python3
"""Bake upcoming events from a Google Calendar into the static site.

Runs from .github/workflows/events-feed.yml. It downloads the calendar's
iCal feed, works out every occurrence (including repeating events), then writes:
  news.html         upcoming events, between EVENTS:START / EVENTS:END
  past-events.html  events that have ended, between PAST_EVENTS:START / END
  events.ics        a public copy of every event on the calendar (past ones stay until
                    deleted from Google Calendar) for "Subscribe to calendar",
                    so the private Google Calendar link is never published

Environment:
  GCAL_ICS_URL     the calendar's "Secret address in iCal format" (GitHub secret)
  EVENT_COUNT      optional, max upcoming events on News (default 6)
  PAST_COUNT       optional, max events on the Past Events page (default 30)

Local testing:
  python .github/scripts/update_events.py --ics calendar.ics [--now 2026-11-20T09:00]

Standard library only; no pip install needed.
"""
import argparse
import html
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SITE_URL = "https://emmy-strong.org"
SITE_TZ = ZoneInfo("America/New_York")
HORIZON_DAYS = 365
WEEKDAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
EMPTY_UPCOMING = ('No upcoming events right now. Follow '
                  '<a href="https://www.instagram.com/emmystrongnj/">@emmystrongnj</a> for new dates.')
EMPTY_PAST = "No past events yet."


# ---------- iCal parsing ----------

def unfold(text):
    return re.sub(r"\r?\n[ \t]", "", text).splitlines()


def unescape(value):
    return re.sub(r"\\([\\;,nN])", lambda m: "\n" if m.group(1) in "nN" else m.group(1), value)


def parse_line(line):
    head, _, value = line.partition(":")
    name, *params = head.split(";")
    return name.upper(), dict(p.split("=", 1) for p in params if "=" in p), value


def parse_dt(value, params):
    """Return (datetime_or_date, is_all_day). Timed values come back timezone-aware."""
    if params.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", value):
        return datetime.strptime(value, "%Y%m%d").date(), True
    dt = datetime.strptime(value.rstrip("Z"), "%Y%m%dT%H%M%S")
    if value.endswith("Z"):
        return dt.replace(tzinfo=timezone.utc), False
    try:
        tz = ZoneInfo(params.get("TZID", "America/New_York"))
    except Exception:
        tz = SITE_TZ
    return dt.replace(tzinfo=tz), False


def parse_events(text):
    events, current = [], None
    for line in unfold(text):
        if line == "BEGIN:VEVENT":
            current = {"exdates": set()}
        elif line == "END:VEVENT" and current is not None:
            if "start" in current:
                events.append(current)
            current = None
        elif current is not None and ":" in line:
            name, params, value = parse_line(line)
            if name == "DTSTART":
                current["start"], current["all_day"] = parse_dt(value, params)
            elif name == "DTEND":
                current["end"], _ = parse_dt(value, params)
            elif name == "RRULE":
                current["rrule"] = dict(p.split("=", 1) for p in value.split(";") if "=" in p)
            elif name == "EXDATE":
                for v in value.split(","):
                    current["exdates"].add(parse_dt(v, params)[0])
            elif name == "RECURRENCE-ID":
                current["recurrence_id"] = parse_dt(value, params)[0]
            elif name in ("SUMMARY", "LOCATION", "DESCRIPTION", "UID", "STATUS", "LAST-MODIFIED"):
                current[name.lower()] = unescape(value)
    return events


# ---------- repeating events ----------

def nth_weekday(year, month, weekday, n):
    """n-th (1-based, or -1 for last) given weekday of a month, or None."""
    first = date(year, month, 1)
    days = [first + timedelta(d) for d in range(31) if (first + timedelta(d)).month == month]
    matches = [d for d in days if d.weekday() == weekday]
    try:
        return matches[n - 1] if n > 0 else matches[n]
    except IndexError:
        return None


def occurrences(ev, until):
    """Yield start values for an event (only the first if it doesn't repeat)."""
    start = ev["start"]
    rule = ev.get("rrule")
    if not rule:
        yield start
        return
    freq = rule.get("FREQ")
    interval = int(rule.get("INTERVAL", 1))
    count = int(rule["COUNT"]) if "COUNT" in rule else None
    end_rule = parse_dt(rule["UNTIL"], {"TZID": "UTC"} if rule["UNTIL"].endswith("Z") else {})[0] if "UNTIL" in rule else None
    all_day = ev["all_day"]
    # Work on local wall-clock time so repeats stay at the same hour across daylight saving.
    tz = None if all_day else start.tzinfo
    local = start if all_day else start.replace(tzinfo=None)
    day0 = local if all_day else local.date()
    clock = None if all_day else local.time()
    byday = rule.get("BYDAY", "").split(",") if rule.get("BYDAY") else []

    def make(d):
        return d if all_day else datetime.combine(d, clock).replace(tzinfo=tz)

    def candidates():
        if freq == "DAILY":
            d = day0
            while True:
                yield d
                d += timedelta(days=interval)
        elif freq == "WEEKLY":
            days = sorted(WEEKDAYS.index(b[-2:]) for b in byday) or [day0.weekday()]
            week = day0 - timedelta(days=day0.weekday())
            while True:
                for wd in days:
                    d = week + timedelta(days=wd)
                    if d >= day0:
                        yield d
                week += timedelta(weeks=interval)
        elif freq in ("MONTHLY", "YEARLY"):
            y, m = day0.year, day0.month
            step = interval if freq == "MONTHLY" else 12 * interval
            while True:
                if byday and re.match(r"[+-]?\d", byday[0]):
                    found = []
                    for b in byday:
                        n, wd = int(b[:-2]), WEEKDAYS.index(b[-2:])
                        d = nth_weekday(y, m, wd, n)
                        if d:
                            found.append(d)
                    for d in sorted(found):
                        if d >= day0:
                            yield d
                else:
                    try:
                        d = date(y, m, day0.day)
                        if d >= day0:
                            yield d
                    except ValueError:
                        pass  # e.g. the 31st in a short month
                m += step
                y, m = y + (m - 1) // 12, (m - 1) % 12 + 1
        else:
            yield day0  # unsupported rule: show the first occurrence only

    produced = 0
    for d in candidates():
        value = make(d)
        if end_rule is not None and compare_key(value) > compare_key(end_rule):
            return
        if compare_key(value) > compare_key(until):
            return
        produced += 1
        if count is not None and produced > count:
            return
        yield value


def compare_key(v):
    """Comparable UTC timestamp for a date or aware datetime."""
    if isinstance(v, datetime):
        return v.astimezone(timezone.utc)
    return datetime.combine(v, time.min).replace(tzinfo=SITE_TZ).astimezone(timezone.utc)


def same_moment(a, b):
    return compare_key(a) == compare_key(b)


def all_occurrences(events, now):
    """Every non-cancelled occurrence still on the calendar, up to HORIZON_DAYS ahead.
    Past events stay until they are deleted from the Google Calendar."""
    until = now + timedelta(days=HORIZON_DAYS)
    overrides = [e for e in events if "recurrence_id" in e]
    results = []
    for ev in events:
        if "recurrence_id" in ev:
            continue
        duration = (ev["end"] - ev["start"]) if "end" in ev else (timedelta(days=1) if ev["all_day"] else timedelta(0))
        for start in occurrences(ev, until):
            if any(same_moment(start, x) for x in ev["exdates"]):
                continue
            item = dict(ev, start=start, end=start + duration)
            for o in overrides:
                if o.get("uid") == ev.get("uid") and same_moment(o["recurrence_id"], start):
                    o_dur = (o["end"] - o["start"]) if "end" in o else duration
                    item = dict(o, end=o["start"] + o_dur)
            results.append(item)
    # One-off changes to a repeating event that moved it outside its normal pattern.
    for o in overrides:
        if not any(r.get("uid") == o.get("uid") and same_moment(r["start"], o["start"]) for r in results):
            o_dur = (o["end"] - o["start"]) if "end" in o else timedelta(0)
            results.append(dict(o, end=o["start"] + o_dur))
    results = [r for r in results
               if r.get("status", "").upper() != "CANCELLED"
               and compare_key(r["start"]) <= until]
    results.sort(key=lambda r: compare_key(r["start"]))
    return results


def end_moment(ev):
    """When an event is over (events with no end time count as over once they start)."""
    return compare_key(ev["end"]) if compare_key(ev["end"]) > compare_key(ev["start"]) else compare_key(ev["start"])


def has_ended(ev, now):
    return end_moment(ev) <= now


# ---------- HTML ----------

def clock(t):
    s = t.strftime("%I:%M %p").lstrip("0")
    return s.replace(":00", "")


def when(ev, with_year=False):
    start, end = ev["start"], ev["end"]
    year = f", {start.year}" if with_year else ""
    if not isinstance(start, datetime):  # all-day (DTEND is exclusive)
        last = end - timedelta(days=1)
        if last <= start:
            return start.strftime("%A, %B ") + str(start.day) + year
        if last.month == start.month:
            return f"{start.strftime('%B')} {start.day}–{last.day}{year}"
        return f"{start.strftime('%B')} {start.day} – {last.strftime('%B')} {last.day}{year}"
    s, e = start.astimezone(SITE_TZ), end.astimezone(SITE_TZ)
    day = s.strftime("%A, %B ") + str(s.day) + (f", {s.year}" if with_year else "")
    if e <= s:
        return f"{day} · {clock(s)}"
    if e.date() != s.date():
        return f"{day} · {clock(s)} – {e.strftime('%a, %b ')}{e.day}, {clock(e)}"
    if s.strftime("%p") == e.strftime("%p"):
        return f"{day} · {clock(s).rsplit(' ', 1)[0]}–{clock(e)}"
    return f"{day} · {clock(s)}–{clock(e)}"


def when_html(ev, with_year=False):
    """Date and time, with the time kept unbroken so it can sit on its own line on phones."""
    text = when(ev, with_year)
    if " · " not in text:
        return f'<span class="nowrap">{html.escape(text)}</span>'
    day, t = text.split(" · ", 1)
    return (f'<span class="nowrap">{html.escape(day)}</span><span class="event-sep"> · </span>'
            f'<span class="event-time nowrap">{html.escape(t)}</span>')


def plain_description(text):
    """Google descriptions may contain HTML; reduce it to plain text."""
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", text or "")
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n\n", text)).strip()


def description_html(text, limit=600):
    text = re.sub(r"\s+", " ", plain_description(text))
    if len(text) > limit:
        text = text[:limit - 3].rsplit(" ", 1)[0] + "…"
    out, pos = [], 0
    for m in re.finditer(r"https?://[^\s<>\"]+[^\s<>\".,;:!?)]", text):
        out.append(html.escape(text[pos:m.start()]))
        url = m.group(0)
        out.append(f'<a href="{html.escape(url)}">{html.escape(url)}</a>')
        pos = m.end()
    out.append(html.escape(text[pos:]))
    return "".join(out)


def iso_local(v):
    return (v.astimezone(SITE_TZ) if isinstance(v, datetime) else v).isoformat()


def render(events, empty_text, past=False):
    """Each event with details is a <details> element, so phones can show just the
    title and date until tapped. It starts open: without JavaScript, and on wider
    screens, everything is visible."""
    empty = f'<p class="note center events-empty"{" hidden" if events else ""}>{empty_text}</p>'
    if not events:
        return f"\n      {empty}\n      "
    items = []
    for ev in events:
        start = ev["start"]
        local = start.astimezone(SITE_TZ) if isinstance(start, datetime) else start
        summary = (
            f'<time class="event-date" datetime="{iso_local(start)}" aria-hidden="true">'
            f'<span class="event-month">{local.strftime("%b")}</span><span class="event-day">{local.day}</span></time>'
            '<span class="event-head">'
            f'<span class="event-title">{html.escape(ev.get("summary") or "EmmyStrong event")}</span>'
            f'<span class="event-when">{when_html(ev, with_year=past)}</span></span>'
        )
        details = []
        loc = (ev.get("location") or "").strip()
        if loc:
            maps = "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(loc)
            details.append(f'<p class="event-where"><a href="{html.escape(maps)}">{html.escape(loc)}</a></p>')
        desc = description_html(ev.get("description"))
        if desc:
            details.append(f"<p>{desc}</p>")
        if details:
            body = (f'<details class="event-toggle" open><summary class="event-summary">{summary}</summary>'
                    f'<div class="event-details">{"".join(details)}</div></details>')
        else:
            body = f'<div class="event-summary">{summary}</div>'
        end_iso = end_moment(ev).astimezone(SITE_TZ).isoformat()
        items.append(f'        <li class="event" data-end="{end_iso}">{body}</li>')
    cls = "event-list event-list-past" if past else "event-list event-list-upcoming"
    return f'\n      <ul class="{cls}">\n' + "\n".join(items) + f"\n      </ul>\n      {empty}\n      "


# ---------- public .ics for "Subscribe" ----------

def ics_escape(text):
    return (text or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def ics_fold(line):
    out, raw = [], line.encode("utf-8")
    while len(raw) > 75:
        cut = 75 if not out else 74
        while cut and (raw[cut] & 0xC0) == 0x80:  # don't split a UTF-8 character
            cut -= 1
        out.append(raw[:cut].decode("utf-8"))
        raw = raw[cut:]
    out.append(raw.decode("utf-8"))
    return "\r\n ".join(out)


def ics_value(v):
    if isinstance(v, datetime):
        return ":" + v.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return ";VALUE=DATE:" + v.strftime("%Y%m%d")


def build_ics(events):
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//EmmyStrong Foundation//Events//EN",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:EmmyStrong Events",
        "X-WR-TIMEZONE:America/New_York", "REFRESH-INTERVAL;VALUE=DURATION:PT1H", "X-PUBLISHED-TTL:PT1H",
    ]
    for ev in events:
        stamp = compare_key(ev["start"]).strftime("%Y%m%dT%H%M%SZ")
        modified = ev.get("last-modified") or stamp  # stable, so the file only changes when events do
        uid = re.sub(r"[^\w.@-]", "", ev.get("uid") or "event")
        lines += ["BEGIN:VEVENT", f"UID:{uid}-{stamp}", f"DTSTAMP:{modified}",
                  "DTSTART" + ics_value(ev["start"]), "DTEND" + ics_value(ev["end"]),
                  "SUMMARY:" + ics_escape(ev.get("summary") or "EmmyStrong event")]
        if ev.get("location"):
            lines.append("LOCATION:" + ics_escape(ev["location"].strip()))
        desc = plain_description(ev.get("description"))
        lines.append("DESCRIPTION:" + ics_escape((desc + "\n\n" if desc else "") + f"{SITE_URL}/news"))
        lines += [f"URL:{SITE_URL}/news", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(ics_fold(l) for l in lines) + "\r\n"


# ---------- output ----------

def write_if_changed(name, content):
    path = os.path.join(ROOT, name)
    try:
        with open(path, encoding="utf-8", newline="") as f:
            if f.read() == content:
                return
    except FileNotFoundError:
        pass
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    print(f"Updated {name}.")


def update_page(page, marker, block):
    path = os.path.join(ROOT, page)
    with open(path, encoding="utf-8", newline="") as f:
        original = f.read()
    pattern = re.compile(rf"(<!-- {marker}:START -->)(.*?)(<!-- {marker}:END -->)", re.S)
    if not pattern.search(original):
        print(f"::warning::No {marker} markers in {page}; skipped.")
        return
    write_if_changed(page, pattern.sub(lambda m: m.group(1) + block + m.group(3), original, count=1))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ics", help="local .ics file, for testing")
    parser.add_argument("--now", help="pretend current time, e.g. 2026-11-20T09:00 (Eastern)")
    args = parser.parse_args()
    count = int(os.environ.get("EVENT_COUNT", "6"))
    past_count = int(os.environ.get("PAST_COUNT", "30"))

    if args.ics:
        with open(args.ics, encoding="utf-8") as f:
            text = f.read()
    else:
        url = os.environ.get("GCAL_ICS_URL", "").strip()
        if not url:
            print("::notice::GCAL_ICS_URL secret is not set yet; skipping the events update.")
            return
        req = urllib.request.Request(url, headers={"User-Agent": "static-site-events-updater"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                text = resp.read().decode("utf-8")
        except Exception as e:  # never print the URL: it is the secret
            sys.exit(f"::error::Could not download the calendar ({type(e).__name__}: {getattr(e, 'code', '')}). "
                     "Check the GCAL_ICS_URL secret.")
        if "BEGIN:VCALENDAR" not in text:
            sys.exit("::error::The calendar link didn't return an iCal file. Check the GCAL_ICS_URL secret.")

    now = (datetime.fromisoformat(args.now).replace(tzinfo=SITE_TZ) if args.now
           else datetime.now(timezone.utc)).astimezone(timezone.utc)
    occ = all_occurrences(parse_events(text), now)
    upcoming = [e for e in occ if not has_ended(e, now)]
    past = [e for e in occ if has_ended(e, now)][::-1]
    print(f"{len(upcoming)} upcoming, {len(past)} past event(s).")

    update_page("news.html", "EVENTS", render(upcoming[:count], EMPTY_UPCOMING))
    update_page("past-events.html", "PAST_EVENTS", render(past[:past_count], EMPTY_PAST, past=True))
    write_if_changed("events.ics", build_ics(occ))  # upcoming and past events


if __name__ == "__main__":
    main()
