"""
Run this script directly from PowerShell to set up Amazon KDP TOTP.
It will:
  1. Open Amazon 2FA settings in Chrome
  2. Extract the TOTP secret key
  3. Save it as GitHub secret KDP_TOTP_SECRET automatically

Usage (from project root):
    .\\venv\\Scripts\\python.exe scripts\\setup_kdp_totp.py
"""
import time
import re
import sys
import json
import base64
import subprocess

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    import pyotp
    from nacl import encoding, public as nacl_public
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Run: pip install undetected-chromedriver pyotp PyNaCl")
    sys.exit(1)

# ── Config ──────────────────────────────────────────────────────────────────
AMAZON_EMAIL    = "harshitasharma99999999@gmail.com"
AMAZON_PASSWORD = "@ABC123xyz"
GITHUB_TOKEN    = ""  # set via env: GITHUB_PAT=your_token
GITHUB_REPO     = "harshitasharma99999999-creator/Printer"
# ─────────────────────────────────────────────────────────────────────────────


def set_github_secret(name: str, value: str):
    import urllib.request, urllib.parse
    # Get public key
    req = urllib.request.Request(
        f"https://api.github.com/repos/{GITHUB_REPO}/actions/secrets/public-key",
        headers={"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"},
    )
    with urllib.request.urlopen(req) as r:
        pk_data = json.loads(r.read())

    pk = nacl_public.PublicKey(pk_data["key"].encode(), encoding.Base64Encoder)
    box = nacl_public.SealedBox(pk)
    encrypted = base64.b64encode(box.encrypt(value.encode())).decode()

    payload = json.dumps({"encrypted_value": encrypted, "key_id": pk_data["key_id"]}).encode()
    req2 = urllib.request.Request(
        f"https://api.github.com/repos/{GITHUB_REPO}/actions/secrets/{name}",
        data=payload,
        method="PUT",
        headers={
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req2) as r:
        print(f"GitHub secret '{name}' set. HTTP {r.status}")


def main():
    print("Opening Chrome for Amazon 2FA setup...")
    print("A browser window will appear — follow the prompts.\n")

    options = uc.ChromeOptions()
    options.add_argument("--window-size=1280,900")
    driver = uc.Chrome(options=options, headless=False, use_subprocess=True, version_main=146)

    try:
        # ── Login ──────────────────────────────────────────────────────────
        driver.get(
            "https://www.amazon.com/ap/signin"
            "?openid.return_to=https://www.amazon.com/a/settings/approval"
            "&openid.assoc_handle=usflex"
            "&openid.mode=checkid_setup"
            "&openid.ns=http://specs.openid.net/auth/2.0"
            "&openid.claimed_id=http://specs.openid.net/auth/2.0/identifier_select"
            "&openid.identity=http://specs.openid.net/auth/2.0/identifier_select"
        )
        time.sleep(4)

        # Email
        for field_id in ["ap_email", "ap_email_login"]:
            try:
                el = WebDriverWait(driver, 8).until(EC.element_to_be_clickable((By.ID, field_id)))
                el.clear(); el.send_keys(AMAZON_EMAIL)
                print("Email entered.")
                break
            except Exception:
                continue
        for btn_id in ["continue", "signInSubmit"]:
            try:
                driver.find_element(By.ID, btn_id).click(); break
            except Exception:
                continue
        time.sleep(3)

        # Password
        try:
            pw = WebDriverWait(driver, 8).until(EC.element_to_be_clickable((By.ID, "ap_password")))
            pw.clear(); pw.send_keys(AMAZON_PASSWORD)
            driver.find_element(By.ID, "signInSubmit").click()
            time.sleep(5)
            print(f"Login attempted. URL: {driver.current_url}")
        except Exception as e:
            print(f"Password step issue: {e}")

        # ── Handle any OTP / phone / email verification ────────────────────
        url = driver.current_url
        if any(x in url for x in ["ap/mfa", "cvf", "verification", "challenge", "auth-mfa", "ax/claim"]):
            print("\n" + "=" * 50)
            print("Amazon wants to verify your identity.")
            print("Check your phone/email for a code.")
            print("=" * 50)
            print(f"Page body:\n{driver.find_element(By.TAG_NAME, 'body').text[:600]}")
            otp = input("\nEnter the verification code Amazon sent: ").strip()
            for sel in ["#auth-mfa-otpcode", "input[name='otpCode']", "input[type='tel']",
                        "input[autocomplete='one-time-code']", "input[type='number']", "input[type='text']"]:
                try:
                    el = driver.find_element(By.CSS_SELECTOR, sel)
                    el.clear(); el.send_keys(otp); break
                except Exception:
                    continue
            for sel in ["#auth-signin-button", "input[type='submit']", "button[type='submit']"]:
                try:
                    driver.find_element(By.CSS_SELECTOR, sel).click(); break
                except Exception:
                    continue
            time.sleep(4)
            print(f"After OTP: {driver.current_url}")

        # ── Navigate to 2FA settings ───────────────────────────────────────
        if "approval" not in driver.current_url:
            driver.get("https://www.amazon.com/a/settings/approval")
            time.sleep(5)

        print(f"\n2FA settings page: {driver.current_url}")
        body = driver.find_element(By.TAG_NAME, "body").text
        print(f"Page:\n{body[:800]}\n")

        print("=" * 50)
        print("LOOK AT THE BROWSER.")
        print("If you see a 'Two-Step Verification' page, press Enter.")
        print("If Amazon asks to verify again, handle it in the browser first,")
        print("then press Enter.")
        print("=" * 50)
        input("Press Enter when ready: ")

        # ── Click 'Add new app' / 'Authenticator app' ─────────────────────
        clicked = False
        for xpath in [
            "//a[contains(text(),'Add new app')]",
            "//button[contains(text(),'Add new app')]",
            "//a[contains(text(),'Authenticator')]",
            "//button[contains(text(),'Authenticator')]",
            "//a[contains(text(),'Get started')]",
            "//button[contains(text(),'Get started')]",
        ]:
            try:
                el = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, xpath)))
                el.click(); time.sleep(4)
                print(f"Clicked: {xpath}")
                clicked = True
                break
            except Exception:
                continue

        if not clicked:
            input("Could not auto-click. Click the authenticator app option in the browser, then press Enter: ")

        # ── QR code page — find text secret ───────────────────────────────
        print("\nLooking for the TOTP secret key on the QR code page...")
        time.sleep(2)
        body2 = driver.find_element(By.TAG_NAME, "body").text
        print(f"QR page:\n{body2[:1000]}\n")

        # Try to click "Can't scan" to reveal text secret
        cant_scan_clicked = False
        for xpath in [
            "//*[contains(text(),\"Can't scan\")]",
            "//*[contains(text(),'Unable to scan')]",
            "//*[contains(text(),'Enter key manually')]",
            "//*[contains(text(),'text code')]",
            "//*[contains(text(),'secret key')]",
        ]:
            try:
                el = driver.find_element(By.XPATH, xpath)
                el.click(); time.sleep(2)
                print(f"Clicked: {xpath}")
                cant_scan_clicked = True
                break
            except Exception:
                continue

        if not cant_scan_clicked:
            print("Click 'Can\\'t scan?' or the text-key option in the browser.")
            input("Press Enter when you can see the text secret key: ")

        time.sleep(2)
        body3 = driver.find_element(By.TAG_NAME, "body").text
        print(f"Page after cant-scan:\n{body3[:2000]}\n")

        # Extract secret
        secret_match = re.search(r'[A-Z2-7]{4}(?:[\s][A-Z2-7]{4}){3,}', body3)
        if secret_match:
            totp_secret = re.sub(r'\s', '', secret_match.group())
            print(f"\nAuto-found secret: {totp_secret}")
        else:
            totp_secret = input("Could not auto-detect. Paste the secret key here: ").strip()
            totp_secret = re.sub(r'[\s\-]', '', totp_secret).upper()

        if not totp_secret:
            print("No secret found. Exiting.")
            return

        # ── Verify and complete setup ──────────────────────────────────────
        otp_code = pyotp.TOTP(totp_secret).now()
        print(f"\nGenerated OTP: {otp_code}")
        print("Submitting to verify the setup...")

        for sel in ["input[type='text']", "input[type='tel']", "input[type='number']",
                    "input[autocomplete='one-time-code']", "#auth-mfa-otpcode"]:
            try:
                el = driver.find_element(By.CSS_SELECTOR, sel)
                el.clear(); el.send_keys(otp_code); break
            except Exception:
                continue

        for xpath in ["//button[contains(text(),'Verify')]", "//button[contains(text(),'Done')]",
                      "//input[@type='submit']", "//button[@type='submit']"]:
            try:
                driver.find_element(By.XPATH, xpath).click(); time.sleep(4); break
            except Exception:
                continue

        print(f"After verify: {driver.current_url}")
        print(driver.find_element(By.TAG_NAME, "body").text[:500])

        # ── Push secret to GitHub ──────────────────────────────────────────
        print(f"\n{'=' * 50}")
        print(f"TOTP SECRET: {totp_secret}")
        print(f"{'=' * 50}")
        print("Saving to GitHub secret KDP_TOTP_SECRET...")
        set_github_secret("KDP_TOTP_SECRET", totp_secret)
        print("Done! KDP_TOTP_SECRET is now set on GitHub.")

        with open("totp_secret_backup.txt", "w") as f:
            f.write(totp_secret)
        print("Backup saved to totp_secret_backup.txt")

    finally:
        input("\nPress Enter to close browser.")
        driver.quit()


if __name__ == "__main__":
    main()
