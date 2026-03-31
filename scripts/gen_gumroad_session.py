"""
Run this ONCE on your local machine to generate Gumroad session cookies.
Paste the output as GitHub secret: GUMROAD_SESSION_JSON

Usage:
    python scripts/gen_gumroad_session.py
"""
import json
import sys
import time

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
except ImportError:
    print("Install selenium first: pip install selenium")
    sys.exit(1)


def main():
    print("Opening Gumroad login in a visible browser window.")
    print("Log in manually, then press Enter here when done.\n")

    options = Options()
    options.add_argument("--window-size=1280,800")
    # Run visible so you can log in manually
    driver = webdriver.Chrome(service=Service(), options=options)

    driver.get("https://app.gumroad.com/login")
    print("Browser opened. Please log in to Gumroad now...")
    print("After logging in successfully, come back here and press Enter.")
    input("Press Enter when you are logged in: ")

    # Verify we're past the login page
    current_url = driver.current_url
    print(f"Current URL: {current_url}")
    if "login" in current_url:
        print("WARNING: Still on login page — make sure you're fully logged in before pressing Enter.")

    # Export all cookies
    cookies = driver.get_cookies()
    driver.quit()

    session_json = json.dumps(cookies, indent=2)
    print("\n" + "=" * 60)
    print("Add this as GitHub secret: GUMROAD_SESSION_JSON")
    print("=" * 60)
    print(session_json)
    print("=" * 60)
    print("\nDone. This session will be reused by GitHub Actions.")


if __name__ == "__main__":
    main()
