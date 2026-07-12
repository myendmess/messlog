"""Upload out.mp4 to YouTube and add it to the motivational playlist.

Reads quote.txt / author.txt for the title & description, and these env vars
(set as GitHub Actions secrets):
    YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN, YT_PLAYLIST_ID

If scripts/localize.py produced localized.json, its translations are attached
as YouTube `localizations` (per-language title/description on the same video)
so viewers in target markets (Indonesia, Philippines, ...) see the quote in
their own language. Localization is strictly optional — any problem with it
falls back to the plain English upload.

The title is prefixed with an incrementing Japanese day counter (一日, 二日, …)
derived from the number of videos already in the playlist.
"""
import json
import os
import re

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# YouTube rejects "<"/">" in titles/descriptions; control chars have no place
# in either. quote.txt ultimately comes from a remote API — sanitize, don't trust.
_UNSAFE = re.compile(r"[<>\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

BASE_HASHTAGS = "#motivation #quotes #shorts #daily #inspiration"
BASE_TAGS = ["motivation", "quotes", "shorts", "daily", "inspiration"]
TAGS_CHAR_BUDGET = 450  # YouTube caps the combined tag list at 500 chars


def sanitize(text):
    return _UNSAFE.sub("", text).strip()


def read(path):
    with open(path, encoding="utf-8") as f:
        return sanitize(f.read())


def to_kanji(n):
    """Integer -> Japanese kanji numerals (1->一, 6->六, 10->十, 100->百, 365->三百六十五)."""
    if n <= 0:
        return "〇"
    if n >= 10000:
        man, rem = divmod(n, 10000)
        return to_kanji(man) + "万" + (to_kanji(rem) if rem else "")
    digits = "〇一二三四五六七八九"
    units = ["", "十", "百", "千"]
    parts = []
    place = 0
    while n > 0:
        d = n % 10
        if d:
            parts.append(units[place] if (d == 1 and place > 0) else digits[d] + units[place])
        n //= 10
        place += 1
    return "".join(reversed(parts))


def playlist_total(youtube, playlist_id):
    resp = youtube.playlistItems().list(
        part="id", playlistId=playlist_id, maxResults=1
    ).execute()
    return resp.get("pageInfo", {}).get("totalResults", 0)


def music_credit():
    """Music credit block for whichever track make_video.sh used.

    Reads track.txt (the chosen .mp3 basename) and looks it up in music.json.
    Returns '' when the track is unknown or the manifest is missing, so an
    upload never fails just because the credit could not be built."""
    try:
        track = read("track.txt")
        with open("music.json", encoding="utf-8") as f:
            meta = json.load(f).get("tracks", {}).get(track)
    except (FileNotFoundError, ValueError):
        return ""
    if not meta:
        return ""
    lines = [f'🎵 Music: {meta["artist"]} — {meta["name"]}']
    if meta.get("spotify_track_id"):
        lines.append(f'Spotify: https://open.spotify.com/track/{meta["spotify_track_id"]}')
    if meta.get("youtube_id"):
        lines.append(f'YouTube: https://youtu.be/{meta["youtube_id"]}')
    return "\n".join(lines) + "\n\n"


def build_title(counter, quote, author):
    # Title mirrors the format of the short that performed well (100+ views):
    #   二日｜"<quote>" — <author> #Shorts   (YouTube caps titles at 100 chars).
    prefix = f"{counter}｜"
    suffix = " #Shorts"
    body = f'"{quote}" — {author}'
    budget = 100 - len(prefix) - len(suffix)
    if len(body) > budget:
        body = body[: budget - 1] + "…"
    return f"{prefix}{body}{suffix}"


def build_description(quote, author, credit, hashtags):
    return f'"{quote}"\n\n— {author}\n\n{credit}{hashtags}'


def load_localizations(counter, author, credit):
    """Per-language title/description from localized.json (if localize.py ran).

    Everything in the file is re-sanitized here — it holds machine output.
    Returns ({lang: {title, description}}, extra_tags). Fail-soft: any problem
    means the video simply ships without localizations."""
    try:
        with open("localized.json", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, ValueError):
        return {}, []
    localizations, extra_tags = {}, []
    for code, m in data.items():
        if not re.fullmatch(r"[a-zA-Z]{2,3}(-[a-zA-Z0-9]{2,8})?", code):
            continue  # only BCP-47-shaped keys reach the API
        quote = sanitize(str(m.get("quote", "")))
        if not quote:
            continue
        hashtags = sanitize(str(m.get("hashtags", ""))) or BASE_HASHTAGS
        localizations[code] = {
            "title": build_title(counter, quote, author),
            "description": build_description(quote, author, credit, hashtags),
        }
        extra_tags += [sanitize(str(t)) for t in m.get("tags", []) if sanitize(str(t))]
    return localizations, extra_tags


def cta_text():
    """Owner-comment CTA: subscribe nudge + the actual track's links + a reply
    hook. Reuses music_credit() so the comment plugs the song really used."""
    return (
        "One quote, every day — subscribe so tomorrow's finds you 🙏\n\n"
        + music_credit()
        + "Which quote should tomorrow bring? Tell me below 👇"
    )


def post_cta_comment(youtube, video_id):
    """Post the CTA as a channel-owner comment on the fresh upload.

    The Data API has no endpoint for pinning — pin it manually in Studio.
    Requires the youtube.force-ssl scope (re-run get_refresh_token.py if the
    stored token predates it)."""
    youtube.commentThreads().insert(
        part="snippet",
        body={
            "snippet": {
                "videoId": video_id,
                "topLevelComment": {"snippet": {"textOriginal": cta_text()}},
            }
        },
    ).execute()


def budget_tags(base, extra):
    """Base tags first, then localized ones while the total stays under budget."""
    tags, used = [], 0
    for t in base + extra:
        if t in tags:
            continue
        if used + len(t) > TAGS_CHAR_BUDGET:
            break
        tags.append(t)
        used += len(t)
    return tags


def main():
    quote = read("quote.txt")
    author = read("author.txt")
    if not quote or not author:
        raise SystemExit("quote.txt/author.txt empty after sanitizing — aborting upload.")

    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=[
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube",
            # Needed to post the CTA comment; tokens minted before this scope
            # was added still upload fine — only the comment step will 403.
            "https://www.googleapis.com/auth/youtube.force-ssl",
        ],
    )
    youtube = build("youtube", "v3", credentials=creds)

    playlist_id = os.environ["YT_PLAYLIST_ID"]
    day = playlist_total(youtube, playlist_id) + 1
    counter = f"{to_kanji(day)}日"
    print(f"Day {day} -> {counter}")

    credit = music_credit()
    localizations, extra_tags = load_localizations(counter, author, credit)

    body = {
        "snippet": {
            "title": build_title(counter, quote, author),
            "description": build_description(quote, author, credit, BASE_HASHTAGS),
            "tags": budget_tags(BASE_TAGS, extra_tags),
            "categoryId": "22",  # People & Blogs
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }
    part = "snippet,status"
    if localizations:
        body["localizations"] = localizations
        part += ",localizations"
        print(f"Localizations: {', '.join(localizations)}")

    print("Uploading video...")
    request = youtube.videos().insert(
        part=part,
        body=body,
        media_body=MediaFileUpload("out.mp4", chunksize=-1, resumable=True, mimetype="video/mp4"),
    )
    # Resumable uploads must be driven with next_chunk() (the official YouTube pattern),
    # not execute(). chunksize=-1 sends the whole file in a single chunk.
    response = None
    while response is None:
        _status, response = request.next_chunk()
    video_id = response["id"]
    print(f"Uploaded: https://youtu.be/{video_id}")

    youtube.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {"kind": "youtube#video", "videoId": video_id},
            }
        },
    ).execute()
    print(f"Added to playlist {playlist_id}")

    # Fail-soft: a missing scope or comment hiccup must never fail the upload.
    try:
        post_cta_comment(youtube, video_id)
        print("CTA comment posted — pin it in Studio when you get a chance.")
    except Exception as e:
        print(f"CTA comment failed ({type(e).__name__}) — post it manually. "
              "If this is a 403, re-run scripts/get_refresh_token.py to mint a "
              "token with the youtube.force-ssl scope and update YT_REFRESH_TOKEN.")


if __name__ == "__main__":
    main()
