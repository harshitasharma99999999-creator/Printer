"""
Generate Instagram session JSON for use as a GitHub secret.
Usage:  python scripts/gen_instagram_session.py
"""
import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

def main():
    try:
        from instagrapi import Client
        from instagrapi.exceptions import ChallengeRequired, TwoFactorRequired
    except ImportError:
        print("Run: pip install instagrapi"); sys.exit(1)

    username = os.environ.get("INSTAGRAM_USERNAME", "").strip()
    password = os.environ.get("INSTAGRAM_PASSWORD", "").strip()
    secret_name = os.environ.get("INSTAGRAM_SECRET_NAME", "INSTAGRAM_SESSION_JSON").strip() or "INSTAGRAM_SESSION_JSON"

    if not username:
        username = input("Instagram username: ").strip()
    if not password:
        password = input("Instagram password: ").strip()

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

    out_file = os.path.join(os.path.dirname(__file__), "..", f"session_{username}.json")
    with open(out_file, "w") as f:
        f.write(session_json)

    print("\n" + "="*60)
    print("SESSION JSON (copy this as your GitHub secret):")
    print("="*60)
    print(session_json)
    print("="*60)
    print(f"\nSaved to: session_{username}.json")
    print("\nGitHub secret command:")
    print(
        f'Get-Content session_{username}.json -Raw | & "C:\\Program Files\\GitHub CLI\\gh.exe" '
        f"secret set {secret_name}"
    )

if __name__ == "__main__":
    main()
