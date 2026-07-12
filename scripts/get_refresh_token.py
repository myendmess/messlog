"""One-time helper: obtain a YouTube refresh token for GitHub Actions.

Run this ONCE on your own machine (not in CI):

    pip install google-auth-oauthlib
    # Put your OAuth "Desktop app" client JSON next to this script as client_secret.json
    python scripts/get_refresh_token.py

A browser window opens for you to sign in with the Google account that owns
the YouTube channel. On success it prints the three values to paste into your
GitHub repo secrets: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN.
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",  # posting the CTA comment
]

flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
# access_type=offline + prompt=consent guarantees a refresh_token is returned.
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

print("\n=== Paste these into GitHub -> Settings -> Secrets and variables -> Actions ===")
print("YT_CLIENT_ID     =", creds.client_id)
print("YT_CLIENT_SECRET =", creds.client_secret)
print("YT_REFRESH_TOKEN =", creds.refresh_token)
