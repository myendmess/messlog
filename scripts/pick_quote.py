"""Pick today's quote from the curated bank and emit the pipeline's inputs.

Reads assets/quotes.json (pre-translated quote bank) and assets/locales.json
(market config), writes:
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
from datetime import date, datetime, timedelta, timezone

# Warn this many days before the localized stretch of the bank runs out. The
# bank is thousands of entries deep but only its first stretch carries
# translations, so multi-market reach ends long before quotes do — and it ends
# silently, one English-only Short at a time, unless something says so first.
LOCALIZATION_RUNWAY_WARN_DAYS = 30

QUOTES_FILE = "assets/quotes.json"
LOCALES_FILE = "assets/locales.json"
OUTPUT_FILE = "localized.json"

# Bank content is committed and reviewed, but sanitize anyway — these strings
# end up in rendered markdown, a commit message, and YouTube metadata.
_UNSAFE = re.compile(r"[<>`\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize(text, limit=300):
    text = _UNSAFE.sub("", str(text))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].strip()


def localization_runway(quotes, idx, codes):
    """How many consecutive upcoming entries still carry a usable translation.

    Counts forward from today's entry and stops at the first one that has no
    translation for any enabled market — that entry is the day the channel
    goes English-only. Returns the number of localized days left, today
    included (0 means today is already English-only)."""
    runway = 0
    for i in range(idx, len(quotes)):
        translations = quotes[i].get("translations") or {}
        if not any(sanitize(translations.get(c, "")) for c in codes):
            break
        runway += 1
    return runway


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

    # Surface the localization cliff. Without this the pipeline degrades in
    # silence: uploads keep succeeding, the run stays green, and every Short
    # quietly reaches only English speakers. ::warning:: puts it on the run
    # summary the same way an exhausted quote bank is flagged.
    codes = [m["code"] for m in markets]
    if not localized:
        print(f"::warning::Entry {idx} has no translations — this Short ships "
              f"English-only to all {len(codes)} enabled markets. "
              "Top up translations in quotes.json.")
        return

    missing = [c for c in codes if c not in localized]
    if missing:
        print(f"::warning::Entry {idx} has no translation for: {', '.join(missing)} "
              f"({len(localized)} of {len(codes)} markets localized).")

    runway = localization_runway(quotes, idx, codes)
    if runway <= LOCALIZATION_RUNWAY_WARN_DAYS:
        last_day = today + timedelta(days=runway - 1)
        print(f"::warning::Only {runway} localized day(s) left in the bank "
              f"(through {last_day}) — after that every Short ships English-only. "
              "Top up translations in quotes.json.")
    else:
        print(f"Localization runway: {runway} days "
              f"(through {today + timedelta(days=runway - 1)}).")


if __name__ == "__main__":
    main()
