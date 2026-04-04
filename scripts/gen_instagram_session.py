"""
Generate Instagram session JSON for use as a GitHub secret.
Run this ONCE on your local machine while logged into the account.

Usage:
    python scripts/gen_instagram_session.py
"""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

def main():
    try:
        from instagrapi import Client
        from instagrapi.exceptions import ChallengeRequired, TwoFactorRequired
    except ImportError:
        print("ERROR: instagrapi not installed. Run: pip install instagrapi")
        sys.exit(1)

    username = input("Instagram username: ").strip()
    password = input("Instagram password: ").strip()

    print(f"\nLogging in as @{username} ...")
    cl = Client()
    cl.delay_range = [1, 3]

    try:
        cl.login(username, password)
    except ChallengeRequired:
        print("\nInstagram requires verification.")

        # Resolve the challenge context first
        try:
            cl.challenge_resolve(cl.last_json)
        except Exception:
            pass

        # Try SMS (phone=0) first, then email (1) as fallback
        sent = False
        for method in (0, 1):
            try:
                cl.challenge_send_code(method)
                label = "phone/SMS" if method == 0 else "email"
                print(f"Verification code sent via {label}. Check now.")
                sent = True
                break
            except Exception:
                continue

        if not sent:
            print("Could not send verification code automatically.")
            print("Check your phone or email manually for a code from Instagram.")

        code = input("Enter verification code: ").strip()
        try:
            cl.challenge_code(code)
        except Exception as e:
            print(f"Challenge code failed: {e}")
            print("\nTry logging in on your phone first, then re-run this script.")
            sys.exit(1)

        # Complete login after challenge
        try:
            cl.login(username, password)
        except Exception:
            pass  # Session may already be active after challenge

    except TwoFactorRequired:
        code = input("Enter your 2FA code: ").strip()
        try:
            cl.two_factor_login(code)
        except Exception as e:
            print(f"2FA login failed: {e}")
            sys.exit(1)
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
