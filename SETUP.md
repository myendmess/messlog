# Daily Quote → YouTube setup

The daily workflow ([.github/workflows/blank.yml](.github/workflows/blank.yml)) already
commits a new quote to `README.md` every day. Once the four secrets below are set, the
same run also renders a vertical Short and publishes it to your **motivational** playlist.

Until the secrets exist, the video steps are skipped automatically — the commit keeps working.

## 1. Create a Google Cloud project + enable the API

1. Go to <https://console.cloud.google.com/> and create a project (any name).
2. **APIs & Services → Library →** search **"YouTube Data API v3" → Enable**.

## 2. Configure the OAuth consent screen

1. **APIs & Services → OAuth consent screen.**
2. User type: **External**. Fill in the app name and your email.
3. **Add yourself as a Test user** (your Google account). Leaving the app in "Testing" is fine.

> Note: refresh tokens for apps in "Testing" mode expire after 7 days. Once it works,
> click **Publish app** on the consent screen to make the token long-lived.

## 3. Create an OAuth client

1. **APIs & Services → Credentials → Create credentials → OAuth client ID.**
2. Application type: **Desktop app**. Create it.
3. **Download JSON** and save it as `client_secret.json` in this folder (it is gitignored).

## 4. Get your refresh token (one time, on your machine)

```bash
pip install google-auth-oauthlib
python scripts/get_refresh_token.py
```

A browser opens — sign in with the account that owns the YouTube channel and approve.
The script prints `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, and `YT_REFRESH_TOKEN`.

## 5. Find your playlist ID

Open the "motivational" playlist on YouTube. The URL looks like:

```
https://www.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxxxx
```

The `YT_PLAYLIST_ID` is everything after `list=` (starts with `PL...`).

## 6. Add the four GitHub secrets

In the repo: **Settings → Secrets and variables → Actions → New repository secret**. Add:

| Secret name        | Value                                  |
| ------------------ | -------------------------------------- |
| `YT_CLIENT_ID`     | from step 4                            |
| `YT_CLIENT_SECRET` | from step 4                            |
| `YT_REFRESH_TOKEN` | from step 4                            |
| `YT_PLAYLIST_ID`   | from step 5 (`PL...`)                  |

## 7. Test it

**Actions → Daily Quote → Run workflow.** Watch the run: it commits the quote, renders
`out.mp4`, uploads it, and adds it to the playlist. The log prints the video URL.

## Notes

- Video: 1080×1920, ~8s, dark background with the wrapped quote + author. Tune colors,
  duration, and fonts in [scripts/make_video.sh](scripts/make_video.sh).
- Uploads are **public**. Change `privacyStatus` to `"unlisted"` or `"private"` in
  [scripts/upload_youtube.py](scripts/upload_youtube.py) while testing.
- Quota: an upload costs ~1600 units of the default 10,000/day YouTube API quota — plenty
  for one video a day.
