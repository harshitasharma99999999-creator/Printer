"""
Run once locally to authorise YouTube upload access.

    cd C:\\Users\\harsh\\MoneyPrinterV2
    venv\\Scripts\\activate
    python scripts/setup_youtube_auth.py

Then copy the contents of token.json into GitHub secret: YOUTUBE_TOKEN_JSON
"""
import os
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # allow http://localhost redirect
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES  = ["https://www.googleapis.com/auth/youtube.upload"]
ROOT    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRETS = os.path.join(ROOT, "client_secrets.json")
TOKEN   = os.path.join(ROOT, "token.json")

flow = InstalledAppFlow.from_client_secrets_file(
    SECRETS, SCOPES, redirect_uri="http://localhost"
)

auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")

print("\n=== STEP 1 ===")
print("Open this URL in your browser:\n")
print(auth_url)
print("\n=== STEP 2 ===")
print("After clicking Allow, your browser will show 'localhost refused to connect'.")
print("That is NORMAL and expected. Do NOT close it.")
print("Copy the FULL URL from the browser address bar and paste it below.\n")

redirect_response = input("Paste the full redirect URL here: ").strip()

flow.fetch_token(authorization_response=redirect_response)
creds = flow.credentials

with open(TOKEN, "w") as f:
    f.write(creds.to_json())

print(f"\nDone! token.json saved at: {TOKEN}")
print("\nNext: copy the full contents of token.json into GitHub secret YOUTUBE_TOKEN_JSON")
print("  repo -> Settings -> Secrets and variables -> Actions -> New repository secret")
