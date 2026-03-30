"""
Run this script ONCE on your LOCAL machine (not in CI) to generate
an Instagram session that GitHub Actions can reuse without triggering
Instagram's suspicious-login block.

Usage:
    pip install instagrapi
    python scripts/gen_instagram_session.py

Then copy the printed JSON and save it as the GitHub secret:
    INSTAGRAM_SESSION_JSON
"""
import json
import sys


def main():
    try:
        from instagrapi import Client
    except ImportError:
        print("ERROR: instagrapi not installed. Run: pip install instagrapi")
        sys.exit(1)

    username = input("Instagram username: ").strip()
    password = input("Instagram password: ").strip()

    print("\nLogging in to Instagram (this may take a few seconds)...")
    cl = Client()
    try:
        cl.login(username, password)
    except Exception as e:
        print(f"\nLogin failed: {e}")
        print("If Instagram asked for a verification code, enter it below.")
        code = input("Verification code (leave blank if not asked): ").strip()
        if code:
            try:
                cl.challenge_resolve(code)
            except Exception as e2:
                print(f"Challenge failed: {e2}")
                sys.exit(1)

    settings = cl.get_settings()
    session_json = json.dumps(settings)

    print("\n" + "=" * 60)
    print("SUCCESS! Copy everything between the lines below and save")
    print("it as GitHub secret: INSTAGRAM_SESSION_JSON")
    print("=" * 60)
    print(session_json)
    print("=" * 60)
    print("\nDone. This session will be reused by GitHub Actions.")


if __name__ == "__main__":
    main()
