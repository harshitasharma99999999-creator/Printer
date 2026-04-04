"""
Generate Instagram session JSON for use as a GitHub secret.
Run this ONCE on your local machine.

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
    except ImportError:
        print("ERROR: instagrapi not installed. Run: pip install instagrapi")
        sys.exit(1)

    username = input("Instagram username: ").strip()
    password = input("Instagram password: ").strip()

    cl = Client()
    cl.delay_range = [1, 3]

    # Set challenge handler BEFORE login — instagrapi calls this automatically
    # when Instagram asks for a verification code
    def challenge_code_handler(username, choice):
        choices = {0: "phone/SMS", 1: "email"}
        label = choices.get(choice, "phone or email")
        print(f"\nInstagram sent a 6-digit code via {label}.")
        print("Check your phone or email now.")
        return input("Enter the code: ").strip()

    cl.challenge_code_handler = challenge_code_handler

    # Set 2FA handler too
    def two_factor_handler(username, two_factor_info):
        return input("\nEnter your 2FA code: ").strip()

    cl.two_factor_code_handler = two_factor_handler

    print(f"\nLogging in as @{username} ...")
    try:
        cl.login(username, password)
    except Exception as e:
        print(f"\nLogin failed: {e}")
        print("\nTroubleshooting:")
        print("  1. Make sure you approved the login on your phone (Instagram app)")
        print("  2. Try logging into Instagram on your phone first, then re-run this script")
        sys.exit(1)

    session = cl.get_settings()
    session_json = json.dumps(session)

    print("\n" + "="*60)
    print("SUCCESS! Copy the JSON below as your GitHub secret:")
    print("="*60)
    print(session_json)
    print("="*60)

    out_file = f"session_{username}.json"
    with open(out_file, "w") as f:
        f.write(session_json)
    print(f"\nAlso saved locally to: {out_file}")
    print("\nGitHub secret to add:")
    print("  Name:  CLOUDK_INSTAGRAM_SESSION_JSON")
    print("  Value: paste the JSON above")

if __name__ == "__main__":
    main()
