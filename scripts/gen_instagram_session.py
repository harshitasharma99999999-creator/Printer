"""
Generate Instagram session JSON for use as a GitHub secret.
Usage:  python scripts/gen_instagram_session.py
"""
import getpass
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

def main():
    try:
        from instagrapi import Client
        from instagrapi.exceptions import ChallengeRequired, TwoFactorRequired
    except ImportError:
        print("Run: pip install instagrapi"); sys.exit(1)

    username = (
        os.environ.get("GRAND_FORNO_INSTAGRAM_USERNAME")
        or os.environ.get("INSTAGRAM_USERNAME")
        or ""
    ).strip()
    password = (
        os.environ.get("GRAND_FORNO_INSTAGRAM_PASSWORD")
        or os.environ.get("INSTAGRAM_PASSWORD")
        or ""
    ).strip()
    secret_name = (
        os.environ.get("INSTAGRAM_SECRET_NAME", "GRAND_FORNO_INSTAGRAM_SESSION_JSON").strip()
        or "GRAND_FORNO_INSTAGRAM_SESSION_JSON"
    )

    if not username:
        username = input("Instagram username: ").strip()
    if not password:
        password = getpass.getpass("Instagram password: ").strip()

    cl = Client()
    cl.delay_range = [1, 3]

    def challenge_code_handler(username, choice):
        label = "phone/SMS" if choice == 0 else "email"
        print(f"\nVerification code sent via {label}. Check now.")
        return input("Enter the 6-digit code: ").strip()

    cl.challenge_code_handler = challenge_code_handler

    print(f"\nLogging in as @{username} ...")

    try:
        cl.login(username, password)

    except ChallengeRequired:
        print("\nInstagram challenge triggered. Resolving...")
        try:
            # This sends the code AND calls challenge_code_handler for the input
            cl.challenge_resolve(cl.last_json)
        except Exception as e:
            print(f"Challenge resolve failed: {e}")
            sys.exit(1)

    except TwoFactorRequired:
        code = input("\nEnter 2FA code: ").strip()
        try:
            cl.two_factor_login(code)
        except Exception as e:
            print(f"2FA failed: {e}"); sys.exit(1)

    except Exception as e:
        print(f"\nLogin failed: {e}"); sys.exit(1)

    session = cl.get_settings()
    session_json = json.dumps(session)

    out_file = Path(__file__).resolve().parents[1] / f"session_{username}.json"
    with out_file.open("w", encoding="utf-8") as f:
        f.write(session_json)

    print("\n" + "="*60)
    print("Instagram session created.")
    print("="*60)
    print(f"\nSaved locally to: {out_file.name}")
    print("This file is ignored by Git. Do not commit or share it.")
    print("\nGitHub secret command:")
    print(
        f'Get-Content {out_file.name} -Raw | & "C:\\Program Files\\GitHub CLI\\gh.exe" '
        f"secret set {secret_name}"
    )

if __name__ == "__main__":
    main()
