"""Pick today's quote from the curated bank and emit the pipeline's inputs.

Reads quotes.json (pre-translated quote bank) and locales.json (market
config), writes:
    quote.txt / author.txt   consumed by make_video.sh and the README commit
    localized.json           consumed by upload_youtube.py (YouTube
                             localizations: per-language title/description)

Selection is deterministic — days since the bank's epoch (UTC), wrapping
modulo the bank size when the runway runs out (a warning is printed so the
log shows it's time to top up). The bank is append-only: adding entries
extends the runway without changing which quote any past day used.

No network, no API keys. Optional argv[1] = YYYY-MM-DD overrides "today"
for local testing.
"""
import json
import re
import sys
from datetime import date, datetime, timezone

QUOTES_FILE = "quotes.json"
LOCALES_FILE = "locales.json"
OUTPUT_FILE = "localized.json"

# Bank content is committed and reviewed, but sanitize anyway — these strings
# end up in rendered markdown, a commit message, and YouTube metadata.
_UNSAFE = re.compile(r"[<>`\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize(text, limit=300):
    text = _UNSAFE.sub("", str(text))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].strip()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def main():
    with open(QUOTES_FILE, encoding="utf-8") as f:
        bank = json.load(f)
    quotes = bank["quotes"]
    epoch = date.fromisoformat(bank["epoch"])

    if len(sys.argv) > 1:
        today = date.fromisoformat(sys.argv[1])
    else:
        today = datetime.now(timezone.utc).date()

    days = max(0, (today - epoch).days)
    idx = days % len(quotes)
    if days >= len(quotes):
        print(f"::warning::Quote bank exhausted (day {days} of {len(quotes)}) — "
              "wrapping around to reuse quotes. Top up quotes.json.")

    entry = quotes[idx]
    quote = sanitize(entry["quote"])
    author = sanitize(entry["author"], 100)
    if not quote or not author:
        raise SystemExit(f"quotes.json entry {idx} is empty after sanitizing.")

    write("quote.txt", quote)
    write("author.txt", author)
    print(f"Day {days} -> entry {idx}: \"{quote}\" — {author}")

    with open(LOCALES_FILE, encoding="utf-8") as f:
        markets = [m for m in json.load(f)["markets"] if m.get("enabled")]

    translations = entry.get("translations", {})
    localized = {}
    for m in markets:
        code = m["code"]
        translated = sanitize(translations.get(code, ""))
        if not translated:
            print(f"[{code}] no translation in the bank for entry {idx} — skipped.")
            continue
        localized[code] = {
            "name": m["name"],
            "market": m["market"],
            "quote": translated,
            "hashtags": sanitize(m.get("hashtags", ""), 200),
            "tags": [sanitize(t, 60) for t in m.get("tags", [])],
        }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(localized, f, ensure_ascii=False, indent=2)
    print(f"Wrote {OUTPUT_FILE} ({', '.join(localized) or 'no locales'})")


if __name__ == "__main__":
    main()
