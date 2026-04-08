"""
Run once locally to authorise YouTube upload access.

    cd C:\\Users\\harsh\\Printer
    python scripts/setup_youtube_auth.py

A browser window will open automatically. Click Allow.
token.json will be saved — copy its contents into GitHub secret YOUTUBE_TOKEN_JSON.
"""
import os
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES  = ["https://www.googleapis.com/auth/youtube.upload"]
ROOT    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRETS = os.path.join(ROOT, "client_secrets.json")
TOKEN   = os.path.join(ROOT, "token.json")

flow = InstalledAppFlow.from_client_secrets_file(SECRETS, SCOPES)

print("\nOpening browser for Google sign-in... (do NOT close it)")
creds = flow.run_local_server(port=0, open_browser=True)

with open(TOKEN, "w") as f:
    f.write(creds.to_json())

print(f"\nDone! token.json saved at: {TOKEN}")
print("\nNext: copy the full contents of token.json into GitHub secret YOUTUBE_TOKEN_JSON")
print("  repo -> Settings -> Secrets and variables -> Actions -> YOUTUBE_TOKEN_JSON -> Update")
print("\nTip: keep token.json private (it contains credentials).")
