"""Upload out.mp4 to YouTube and add it to the motivational playlist.

Reads quote.txt / author.txt for the title & description, and these env vars
(set as GitHub Actions secrets):
    YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN, YT_PLAYLIST_ID
"""
import os

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


quote = read("quote.txt")
author = read("author.txt")

# YouTube titles: max 100 chars, no "<" or ">".
title = f'"{quote}" — {author}'.replace("<", "").replace(">", "")
if len(title) > 90:
    title = title[:87] + "..."
title = f"{title} #Shorts"

description = f'"{quote}"\n\n— {author}\n\n#motivation #quotes #shorts #daily #inspiration'

creds = Credentials(
    None,
    refresh_token=os.environ["YT_REFRESH_TOKEN"],
    token_uri="https://oauth2.googleapis.com/token",
    client_id=os.environ["YT_CLIENT_ID"],
    client_secret=os.environ["YT_CLIENT_SECRET"],
    scopes=[
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube",
    ],
)

youtube = build("youtube", "v3", credentials=creds)

print("Uploading video...")
request = youtube.videos().insert(
    part="snippet,status",
    body={
        "snippet": {
            "title": title,
            "description": description,
            "tags": ["motivation", "quotes", "shorts", "daily", "inspiration"],
            "categoryId": "22",  # People & Blogs
        },
        "status": {
            "privacyStatus": "unlisted",
            "selfDeclaredMadeForKids": False,
        },
    },
    media_body=MediaFileUpload("out.mp4", chunksize=-1, resumable=True, mimetype="video/mp4"),
)
# Resumable uploads must be driven with next_chunk() (the official YouTube pattern),
# not execute(). chunksize=-1 sends the whole file in a single chunk.
response = None
while response is None:
    _status, response = request.next_chunk()
video_id = response["id"]
print(f"Uploaded: https://youtu.be/{video_id}")

playlist_id = os.environ["YT_PLAYLIST_ID"]
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
