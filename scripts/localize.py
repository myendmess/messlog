"""Translate the daily quote for the target markets in locales.json.

Writes localized.json, which upload_youtube.py attaches to the daily upload as
YouTube `localizations` metadata — one video, per-language title/description,
no extra renders. Author names are left untranslated (proper nouns).

Env (set as GitHub Actions secrets — never hardcode keys):
    TRANSLATE_API_KEY   Google Cloud Translation API key. Absent -> step skips.
    TRANSLATE_PROVIDER  'google' (default) or 'none' (skip).

Fail-soft by design: a failed translation skips that locale, a missing key
skips the whole step, and nothing here can block the English upload.
Stdlib only — no extra pip dependencies in CI.
"""
import html
import json
import os
import re
import sys
import urllib.request

LOCALES_FILE = "locales.json"
OUTPUT_FILE = "localized.json"
MAX_QUOTE_CHARS = 300
HTTP_TIMEOUT = 15

# Control chars and angle brackets are stripped everywhere: quote text comes
# from a remote API and translations from another — treat both as untrusted.
_UNSAFE = re.compile(r"[<>\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize(text, limit=MAX_QUOTE_CHARS):
    text = _UNSAFE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].strip()


def translate_google(text, target, api_key):
    """Google Cloud Translation v2. Key goes in a header, never the URL."""
    req = urllib.request.Request(
        "https://translation.googleapis.com/language/translate/v2",
        data=json.dumps(
            {"q": text, "source": "en", "target": target, "format": "text"}
        ).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-goog-api-key": api_key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        payload = json.load(resp)
    translated = payload["data"]["translations"][0]["translatedText"]
    return html.unescape(translated)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


def main():
    # Never let a stale file from an earlier run leak old translations.
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)

    provider = os.environ.get("TRANSLATE_PROVIDER", "google")
    api_key = os.environ.get("TRANSLATE_API_KEY", "")
    if provider == "none" or not api_key:
        print("No translation provider/key configured — skipping localization.")
        return 0
    if provider != "google":
        print(f"Unknown TRANSLATE_PROVIDER '{provider}' — skipping localization.")
        return 0

    quote = sanitize(read("quote.txt"))
    if not quote:
        print("Empty quote — skipping localization.")
        return 0

    with open(LOCALES_FILE, encoding="utf-8") as f:
        markets = [m for m in json.load(f)["markets"] if m.get("enabled")]
    if not markets:
        print("No markets enabled in locales.json — nothing to do.")
        return 0

    localized = {}
    for m in markets:
        code = m["code"]
        try:
            translated = sanitize(
                translate_google(quote, m.get("translate_code", code), api_key)
            )
        except Exception as e:  # fail-soft: skip locale, never block the upload
            print(f"[{code}] translation failed ({type(e).__name__}) — skipped.")
            continue
        if not translated:
            print(f"[{code}] empty translation — skipped.")
            continue
        localized[code] = {
            "name": m["name"],
            "market": m["market"],
            "quote": translated,
            "hashtags": sanitize(m.get("hashtags", ""), 200),
            "tags": [sanitize(t, 60) for t in m.get("tags", [])],
        }
        print(f"[{code}] {m['market']}: ok")

    if not localized:
        print("No locale succeeded — localized.json not written.")
        return 0

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(localized, f, ensure_ascii=False, indent=2)
    print(f"Wrote {OUTPUT_FILE} ({', '.join(localized)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
