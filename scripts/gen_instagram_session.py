"""
Generate Instagram session JSON for use as a GitHub secret.
Run this ONCE on your local machine while logged into the account.

Usage:
    python scripts/gen_instagram_session.py

Then copy the printed JSON and save it as a GitHub secret.
"""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

def main():
    try:
        from instagrapi import Client
    except ImportError:
        print("ERROR: instagrapi not installed.")
        print("Run:  pip install instagrapi")
        sys.exit(1)

    username = input("Instagram username: ").strip()
    password = input("Instagram password: ").strip()

    print(f"\nLogging in as @{username} ...")
    cl = Client()
    cl.delay_range = [1, 3]

    try:
        cl.login(username, password)
    except Exception as e:
        print(f"\nLogin failed: {e}")
        sys.exit(1)

    session = cl.get_settings()
    session_json = json.dumps(session)

    print("\n" + "="*60)
    print("SESSION JSON — copy this as your GitHub secret:")
    print("="*60)
    print(session_json)
    print("="*60)

    out_file = f"session_{username}.json"
    with open(out_file, "w") as f:
        f.write(session_json)
    print(f"\nAlso saved locally to: {out_file}")
    print("\nAdd as GitHub secret:")
    print("  Name:  CLOUDK_INSTAGRAM_SESSION_JSON")
    print("  Value: paste the JSON above")

if __name__ == "__main__":
    main()
