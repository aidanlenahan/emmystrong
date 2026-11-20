#!/usr/bin/env python3
"""Fetch the latest Instagram posts and bake them into the static site.

Runs daily from .github/workflows/instagram-feed.yml. It:
  1. Refreshes the long-lived access token (keeps it from expiring after 60 days).
  2. Fetches the newest posts from the Instagram API (Instagram Login).
  3. Downloads each post's image into media/instagram/ (Instagram's own image
     URLs expire, so the site serves its own copies).
  4. Rewrites the HTML between the INSTAGRAM:START / INSTAGRAM:END markers in
     the target pages, so the feed is plain static HTML with no Instagram scripts.
  5. Removes images of posts that dropped out of the feed.

Environment:
  IG_ACCESS_TOKEN   access token (GitHub secret): an Instagram Login token ("IG...",
                    refreshed each run) or a Unified login system-user token ("EAA...")
  IG_USER_ID        Instagram account ID, required for "EAA..." tokens
  IG_POST_COUNT     optional, number of posts to show (default 6)

Local testing without a token:
  python .github/scripts/update_instagram.py --sample sample.json
  where sample.json is a list of {"id","caption","permalink","image"} objects;
  "image" is a path to an existing local file.

Standard library only; no pip install needed.
"""
import argparse
import html
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MEDIA_DIR = os.path.join(ROOT, "media", "instagram")
MEDIA_URL = "media/instagram"  # relative, so the page also previews correctly from file://
PAGES = ["index.html", "news.html", "events.html"]
PROFILE_URL = "https://www.instagram.com/emmystrongnj/"
API = "https://graph.instagram.com"           # Instagram Login tokens (start with "IG")
FB_API = "https://graph.facebook.com"   # Unified login / system-user tokens (start with "EAA"). Unversioned: Meta picks a supported version.
MARKER = re.compile(r"(<!-- INSTAGRAM:START -->)(.*?)(<!-- INSTAGRAM:END -->)", re.S)


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "static-site-feed-updater"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        # Surface Instagram's error message (it never echoes the token back).
        try:
            detail = json.load(e).get("error", {})
            msg = f"{detail.get('type', '')} {detail.get('code', '')}: {detail.get('message', '')}".strip()
        except Exception:
            msg = ""
        raise RuntimeError(f"HTTP {e.code} from Instagram API. {msg}") from None


def refresh_token(token):
    """Extend the token's 60-day lifetime. Tokens must be at least 24h old to refresh."""
    url = f"{API}/refresh_access_token?" + urllib.parse.urlencode(
        {"grant_type": "ig_refresh_token", "access_token": token})
    try:
        data = get_json(url)
        days = int(data.get("expires_in", 0)) // 86400
        print(f"Token refreshed; valid for about {days} more days.")
        if data.get("access_token") and data["access_token"] != token:
            print("::warning::Instagram returned a new token string. Update the IG_ACCESS_TOKEN secret.")
    except Exception as e:  # a failed refresh shouldn't block the feed update
        print(f"::warning::Token refresh failed: {e}")


def fetch_posts(token, count, user_id=None):
    fields = "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp"
    base = f"{FB_API}/{user_id}" if user_id else f"{API}/me"
    url = f"{base}/media?" + urllib.parse.urlencode(
        {"fields": fields, "limit": count, "access_token": token})
    posts = []
    for item in get_json(url).get("data", [])[:count]:
        image = item.get("thumbnail_url") if item.get("media_type") == "VIDEO" else item.get("media_url")
        if not image:
            continue
        posts.append({
            "id": item["id"],
            "caption": item.get("caption", ""),
            "permalink": item["permalink"],
            "image": image,
            "is_video": item.get("media_type") == "VIDEO",
        })
    return posts


def save_image(src, post_id):
    os.makedirs(MEDIA_DIR, exist_ok=True)
    filename = f"{post_id}.jpg"
    dest = os.path.join(MEDIA_DIR, filename)
    if os.path.exists(dest):
        return filename
    if re.match(r"https?://", src):
        req = urllib.request.Request(src, headers={"User-Agent": "static-site-feed-updater"})
        with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as out:
            shutil.copyfileobj(resp, out)
    else:
        shutil.copyfile(src, dest)
    return filename


def alt_text(caption):
    text = re.sub(r"\s+", " ", re.sub(r"#\w+", "", caption or "")).strip()
    if len(text) > 120:
        text = text[:117].rsplit(" ", 1)[0] + "…"
    return text or "EmmyStrong Instagram post"


def render(posts):
    items = []
    for p in posts:
        label = "Video" if p.get("is_video") else "Post"
        text = html.escape(alt_text(p["caption"]))
        items.append(
            f'        <li><a href="{html.escape(p["permalink"])}" aria-label="{label} on Instagram: {text}">'
            f'<img src="{MEDIA_URL}/{p["file"]}" alt="" width="320" height="320" loading="lazy" decoding="async">'
            f'<span class="ig-caption" aria-hidden="true"><span>{text}</span></span></a></li>'
        )
    return (
        "\n      <ul class=\"ig-grid\">\n" + "\n".join(items) + "\n      </ul>\n      "
    )


def update_pages(block):
    changed = False
    for page in PAGES:
        path = os.path.join(ROOT, page)
        with open(path, encoding="utf-8") as f:
            original = f.read()
        if not MARKER.search(original):
            print(f"::warning::No INSTAGRAM markers in {page}; skipped.")
            continue
        updated = MARKER.sub(lambda m: m.group(1) + block + m.group(3), original, count=1)
        if updated != original:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(updated)
            changed = True
            print(f"Updated {page}.")
    return changed


def prune(keep):
    if not os.path.isdir(MEDIA_DIR):
        return
    for name in os.listdir(MEDIA_DIR):
        if name.endswith(".jpg") and name not in keep:
            os.remove(os.path.join(MEDIA_DIR, name))
            print(f"Removed old image {name}.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", help="JSON file of sample posts, for local testing")
    args = parser.parse_args()
    count = int(os.environ.get("IG_POST_COUNT", "6"))

    if args.sample:
        with open(args.sample, encoding="utf-8") as f:
            posts = json.load(f)[:count]
    else:
        token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
        if not token:
            print("::notice::IG_ACCESS_TOKEN secret is not set yet; skipping the Instagram feed update.")
            return
        user_id = None
        if token.startswith("EAA"):
            # System-user token from Meta's Unified login: never expires, read via the Facebook Graph API.
            user_id = os.environ.get("IG_USER_ID", "").strip()
            if not user_id:
                sys.exit("::error::IG_USER_ID is required with a Unified login (EAA...) token.")
        else:
            refresh_token(token)
        try:
            posts = fetch_posts(token, count, user_id)
        except RuntimeError as e:
            sys.exit(f"::error::Could not fetch posts. {e}")

    if not posts:
        sys.exit("No posts returned; leaving the site unchanged.")

    for p in posts:
        p["file"] = save_image(p["image"], p["id"])
    update_pages(render(posts))
    prune({p["file"] for p in posts})


if __name__ == "__main__":
    main()
