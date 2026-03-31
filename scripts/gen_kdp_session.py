"""
Run this ONCE on your local machine to generate Amazon KDP session cookies.
Paste the output as GitHub secret: KDP_SESSION_JSON

Usage:
    .\\venv\\Scripts\\python.exe scripts\\gen_kdp_session.py
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
    print("Opening KDP login in a visible browser window.")
    print("Log in manually (complete any 2FA/OTP), then press Enter here when done.\n")

    options = Options()
    options.add_argument("--window-size=1280,800")
    driver = webdriver.Chrome(service=Service(), options=options)

    driver.get("https://kdp.amazon.com/")
    print("Browser opened. Please log in to KDP now...")
    print("Tip: tick 'Keep me signed in' so the session lasts longer.")
    print("After logging in successfully and seeing the KDP dashboard, come back here.")
    input("Press Enter when you are fully logged in to KDP: ")

    current_url = driver.current_url
    print(f"Current URL: {current_url}")
    if "signin" in current_url or "login" in current_url:
        print("WARNING: Still on login page — make sure you are fully logged in before pressing Enter.")

    # Export cookies for both amazon.com and kdp.amazon.com
    all_cookies = []
    for domain in ["https://www.amazon.com", "https://kdp.amazon.com"]:
        driver.get(domain)
        time.sleep(2)
        all_cookies.extend(driver.get_cookies())

    driver.quit()

    # Deduplicate by (name, domain)
    seen = set()
    unique_cookies = []
    for c in all_cookies:
        key = (c.get("name"), c.get("domain", ""))
        if key not in seen:
            seen.add(key)
            unique_cookies.append(c)

    session_json = json.dumps(unique_cookies, indent=2)
    print("\n" + "=" * 60)
    print("Add this as GitHub secret: KDP_SESSION_JSON")
    print("=" * 60)
    print(session_json)
    print("=" * 60)
    print("\nDone. This session will be reused by GitHub Actions.")


if __name__ == "__main__":
    main()
