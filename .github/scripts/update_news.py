#!/usr/bin/env python3
"""Bake news posts from a Google Sheet into news.html.

Runs from .github/workflows/news-feed.yml. It downloads the sheet (published
to the web as CSV), and rewrites the HTML between NEWS:START / NEWS:END.

Sheet columns (first row is the header; order doesn't matter, case doesn't matter):
  Date       when the post goes up. Posts dated in the future stay hidden until then.
  Title      headline
  Text       body. A blank line starts a new paragraph; web addresses become links.
  Link       optional, a button at the bottom of the post
  Link Text  optional, the button's label (default "Learn more")
  Image      optional, an image URL or a Google Drive share link
             (the Drive file must be shared as "Anyone with the link")
  Show       optional, "no" hides the post

Environment:
  NEWS_CSV_URL   the sheet's "Publish to web" CSV link (GitHub secret)
  NEWS_COUNT     optional, max posts to show (default 10)

Local testing:
  python .github/scripts/update_news.py --csv news.csv [--now 2026-11-20]

Standard library only; no pip install needed.
"""
import argparse
import csv
import hashlib
import html
import io
import os
import re
import sys
import urllib.request
from datetime import date, datetime
from zoneinfo import ZoneInfo

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PAGE = "news.html"
IMG_DIR = "media/news"
SITE_TZ = ZoneInfo("America/New_York")
MAX_IMAGE_BYTES = 8 * 1024 * 1024
IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}
MARKER = re.compile(r"(<!-- NEWS:START -->)(.*?)(<!-- NEWS:END -->)", re.S)
URL_RE = re.compile(r"https?://[^\s<>\"]+[^\s<>\".,;:!?)]")
EMPTY = ('<p class="note center">No news yet. Follow '
         '<a href="https://www.instagram.com/emmystrongnj/">@emmystrongnj</a> for updates.</p>')
UA = {"User-Agent": "static-site-news-updater"}


def fetch(url, timeout=30):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as resp:
        return resp.read(MAX_IMAGE_BYTES + 1), resp.headers.get_content_type()


def parse_date(value):
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%B %d, %Y", "%b %d, %Y", "%Y-%m-%d %H:%M:%S",
                "%m/%d/%Y %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None


def read_posts(text, today):
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return []
    header = [h.strip().lower() for h in rows[0]]
    posts = []
    for n, row in enumerate(rows[1:], start=2):
        r = {header[i]: v.strip() for i, v in enumerate(row) if i < len(header)}
        if not (r.get("title") or r.get("text")):
            continue
        if r.get("show", "").lower() in ("no", "n", "false", "hide", "hidden"):
            continue
        d = parse_date(r.get("date", ""))
        if r.get("date") and not d:
            print(f"::warning::Row {n}: couldn't read the date {r['date']!r}; use a date like 11/20/2026.")
        if d and d > today:
            continue  # scheduled for later
        r["_date"] = d
        r["_row"] = n
        posts.append(r)
    # Newest first; undated posts go last, in sheet order.
    posts.sort(key=lambda p: (p["_date"] is not None, p["_date"] or date.min), reverse=True)
    return posts


def drive_id(url):
    m = re.search(r"drive\.google\.com/(?:file/d/|open\?id=|uc\?(?:.*&)?id=)([\w-]+)", url)
    return m.group(1) if m else None


def save_image(url, row):
    """Download the image into media/news and return its path, or None."""
    fid = drive_id(url)
    src = f"https://drive.google.com/uc?export=download&id={fid}" if fid else url
    name = hashlib.sha1(src.encode()).hexdigest()[:16]
    for ext in IMAGE_TYPES.values():  # already downloaded
        if os.path.exists(os.path.join(ROOT, IMG_DIR, name + ext)):
            return f"{IMG_DIR}/{name}{ext}"
    try:
        data, ctype = fetch(src)
    except Exception as e:
        print(f"::warning::Row {row}: couldn't download the image ({type(e).__name__}). Skipping it.")
        return None
    if ctype not in IMAGE_TYPES:
        hint = " Share the Drive file as \"Anyone with the link\"." if fid else ""
        print(f"::warning::Row {row}: the Image link isn't a picture (got {ctype}).{hint} Skipping it.")
        return None
    if len(data) > MAX_IMAGE_BYTES:
        print(f"::warning::Row {row}: the image is over 8 MB. Skipping it.")
        return None
    os.makedirs(os.path.join(ROOT, IMG_DIR), exist_ok=True)
    path = f"{IMG_DIR}/{name}{IMAGE_TYPES[ctype]}"
    with open(os.path.join(ROOT, path), "wb") as f:
        f.write(data)
    return path


def text_html(text):
    out = []
    for para in re.split(r"\n\s*\n", text.strip()):
        parts, last = [], 0
        for m in URL_RE.finditer(para):
            parts.append(html.escape(para[last:m.start()]))
            parts.append(f'<a href="{html.escape(m.group(0))}">{html.escape(m.group(0))}</a>')
            last = m.end()
        parts.append(html.escape(para[last:]))
        out.append("<p>" + "".join(parts).replace("\n", "<br>") + "</p>")
    return "".join(out)


def safe_link(url):
    return url if re.match(r"(https?://|mailto:|/)", url) else ("https://" + url if "." in url else "")


def render(posts, images):
    if not posts:
        return "\n      " + EMPTY + "\n      "
    items = []
    for p in posts:
        parts = []
        img = images.get(p["_row"])
        if img:
            parts.append(f'<img class="news-image" src="{img}" alt="" loading="lazy" decoding="async">')
        body = []
        if p["_date"]:
            d = p["_date"]
            body.append(f'<time class="news-date" datetime="{d.isoformat()}">{d:%B} {d.day}, {d.year}</time>')
        if p.get("title"):
            body.append(f'<h3 class="news-title">{html.escape(p["title"])}</h3>')
        if p.get("text"):
            body.append(text_html(p["text"]))
        link = safe_link(p.get("link", ""))
        if link:
            label = html.escape(p.get("link text") or "Learn more")
            body.append(f'<p class="news-cta"><a class="btn btn-outline" href="{html.escape(link)}">{label}</a></p>')
        parts.append('<div class="news-body">' + "".join(body) + "</div>")
        items.append('        <article class="news-item">' + "".join(parts) + "</article>")
    return '\n      <div class="news-list">\n' + "\n".join(items) + "\n      </div>\n      "


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", help="local .csv file, for testing")
    parser.add_argument("--now", help="pretend today's date, e.g. 2026-11-20")
    args = parser.parse_args()
    count = int(os.environ.get("NEWS_COUNT", "10"))

    if args.csv:
        with open(args.csv, encoding="utf-8") as f:
            text = f.read()
    else:
        url = os.environ.get("NEWS_CSV_URL", "").strip()
        if not url:
            print("::notice::NEWS_CSV_URL secret is not set yet; skipping the news update.")
            return
        try:
            data, ctype = fetch(url)
        except Exception as e:
            sys.exit(f"::error::Could not download the news sheet ({type(e).__name__}: {getattr(e, 'code', '')}). "
                     "Check the NEWS_CSV_URL secret.")
        text = data.decode("utf-8-sig")
        if ctype == "text/html" or text.lstrip().startswith("<"):
            sys.exit("::error::The news link returned a web page, not CSV. Publish the sheet as "
                     "\"Comma-separated values (.csv)\" and update the NEWS_CSV_URL secret.")

    today = date.fromisoformat(args.now) if args.now else datetime.now(SITE_TZ).date()
    posts = read_posts(text, today)[:count]
    images = {}
    for p in posts:
        if p.get("image"):
            path = save_image(p["image"], p["_row"])
            if path:
                images[p["_row"]] = path
    print(f"{len(posts)} news post(s), {len(images)} image(s).")

    # Remove images no longer used by any post.
    img_root = os.path.join(ROOT, IMG_DIR)
    if os.path.isdir(img_root):
        keep = {os.path.basename(p) for p in images.values()}
        for f in os.listdir(img_root):
            if f not in keep and f != ".gitkeep":
                os.remove(os.path.join(img_root, f))

    path = os.path.join(ROOT, PAGE)
    with open(path, encoding="utf-8", newline="") as f:
        original = f.read()
    if not MARKER.search(original):
        sys.exit(f"::error::No NEWS markers in {PAGE}.")
    block = render(posts, images)
    updated = MARKER.sub(lambda m: m.group(1) + block + m.group(3), original, count=1)
    if updated != original:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(updated)
        print(f"Updated {PAGE}.")
    else:
        print(f"{PAGE} already up to date.")


if __name__ == "__main__":
    main()
