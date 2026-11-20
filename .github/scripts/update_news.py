#!/usr/bin/env python3
"""Bake news posts from a Google Sheet into news.html.

Runs from .github/workflows/news-feed.yml. It downloads the sheet (published
to the web as CSV), and rewrites the HTML between NEWS:START / NEWS:END.

Sheet columns (first row is the header; order doesn't matter, case doesn't matter):
  Date       when the post goes up. Posts dated in the future stay hidden until then.
  Title      headline
  Text       body. A blank line starts a new paragraph; web addresses become links.
  Link, Link 2, Link 3
             optional, buttons at the bottom of the post
  Link Text, Link 2 Text, Link 3 Text
             optional, each button's label (default "Learn more")
  Image, Image 2 ... Image 5
             optional, image URLs or Google Drive share links (the Drive file
             must be shared as "Anyone with the link"). More than one image
             shows as a slideshow. Pictures are never cropped: the leftover
             space is filled with a blurred copy of the picture.
  Show       optional, "no" hides the post

Environment:
  NEWS_CSV_URL   the sheet's "Publish to web" CSV link (GitHub secret)
  NEWS_COUNT     optional, max posts to show (default 10)

Local testing:
  python .github/scripts/update_news.py --csv news.csv [--now 2026-11-20]

Needs Pillow for image optimization (installed by the workflow); without it,
images are kept as they are.
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

from image_opt import optimize  # same folder; Python puts the script's folder on the path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PAGE = "news.html"
IMG_DIR = "media/news"
SITE_TZ = ZoneInfo("America/New_York")
MAX_IMAGE_BYTES = 25 * 1024 * 1024  # big phone photos are fine; they get shrunk
IMAGE_MAX_WIDTH = 1600  # wide enough for the full-post view on large screens
IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}
MARKER = re.compile(r"(<!-- NEWS:START -->)(.*?)(<!-- NEWS:END -->)", re.S)
URL_RE = re.compile(r"https?://[^\s<>\"]+[^\s<>\".,;:!?)]")
EMPTY = ('<p class="note center">No news yet. Follow '
         '<a href="https://www.instagram.com/emmystrongnj/">@emmystrongnj</a> for updates.</p>')
IMAGE_COLUMNS = ["image", "image 2", "image 3", "image 4", "image 5"]
LINK_COLUMNS = [("link", "link text"), ("link 2", "link 2 text"), ("link 3", "link 3 text")]
# Some image hosts (Wikimedia, for one) refuse downloads that don't say who's asking.
UA = {"User-Agent": "EmmyStrongSiteBot/1.0 (+https://emmy-strong.org; news image fetcher)"}


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
    m = re.search(r"drive\.google\.com/(?:file/d/|open\?id=|uc\?(?:.*&)?id=|thumbnail\?(?:.*&)?id=)([\w-]+)"
                  r"|drive\.usercontent\.google\.com/download\?(?:.*&)?id=([\w-]+)", url)
    return (m.group(1) or m.group(2)) if m else None


def save_image(url, row, column):
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
        code = getattr(e, "code", None)
        why = f"the site hosting it refused the download (HTTP {code})" if code else type(e).__name__
        print(f"::warning::Row {row}, {column}: couldn't download the image: {why}. Skipping it. "
              "Tip: upload the picture to Google Drive, share it as \"Anyone with the link\", and use that link.")
        return None
    if ctype not in IMAGE_TYPES:
        hint = " Share the Drive file as \"Anyone with the link\"." if fid else ""
        print(f"::warning::Row {row}, {column}: the link isn't a picture (got {ctype}).{hint} Skipping it.")
        return None
    if len(data) > MAX_IMAGE_BYTES:
        print(f"::warning::Row {row}, {column}: the image is over 25 MB. Skipping it.")
        return None
    data, ext = optimize(data, IMAGE_MAX_WIDTH, IMAGE_TYPES[ctype])  # WebP, resized
    os.makedirs(os.path.join(ROOT, IMG_DIR), exist_ok=True)
    path = f"{IMG_DIR}/{name}{ext}"
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


def media_html(paths):
    """Pictures for a post. Each sits uncropped over a blurred copy of itself;
    two or more become a slideshow (buttons and dots are added by js/script.js)."""
    if not paths:
        return ""
    slides = "".join(
        f'<figure class="news-slide"><span class="news-blur" style="background-image:url(\'{path}\')"></span>'
        f'<img src="{path}" alt="" loading="lazy" decoding="async"></figure>'
        for path in paths
    )
    many = " news-carousel" if len(paths) > 1 else ""
    return f'<div class="news-media{many}"><div class="news-track">{slides}</div></div>'


def render(posts, images):
    if not posts:
        return "\n      " + EMPTY + "\n      "
    items = []
    for p in posts:
        parts = []
        if p["_date"]:
            d = p["_date"]
            parts.append(f'<time class="news-date" datetime="{d.isoformat()}">{d:%B} {d.day}, {d.year}</time>')
        if p.get("title"):
            parts.append(f'<h3 class="news-title">{html.escape(p["title"])}</h3>')
        if p.get("text"):
            # Cut to a few lines on the card; "Read more" opens the whole post (see js/script.js).
            parts.append('<div class="news-text">' + text_html(p["text"]) + "</div>")
            parts.append('<button type="button" class="news-more" hidden>Read more</button>')
        buttons = []
        for link_col, text_col in LINK_COLUMNS:
            link = safe_link(p.get(link_col, ""))
            if link:
                label = html.escape(p.get(text_col) or "Learn more")
                buttons.append(f'<a class="btn btn-outline" href="{html.escape(link)}">{label}</a>')
        if buttons:
            parts.append('<p class="news-cta">' + "".join(buttons) + "</p>")
        items.append('        <article class="news-item">' + media_html(images.get(p["_row"], []))
                     + '<div class="news-body">' + "".join(parts) + "</div></article>")
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
        paths = []
        for col in IMAGE_COLUMNS:
            if p.get(col):
                path = save_image(p[col], p["_row"], col.title())
                if path and path not in paths:
                    paths.append(path)
        if paths:
            images[p["_row"]] = paths
    print(f"{len(posts)} news post(s), {sum(map(len, images.values()))} image(s).")

    # Remove images no longer used by any post.
    img_root = os.path.join(ROOT, IMG_DIR)
    if os.path.isdir(img_root):
        keep = {os.path.basename(p) for paths in images.values() for p in paths}
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
