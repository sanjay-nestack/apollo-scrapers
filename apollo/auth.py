"""Authentication / session-open seam. login_if_needed is the ONLY login path;
it still creates its own local wait and still blocks on input() (unchanged)."""
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Accounts skipped at the top of the loop (no driver opened).
HARDCODED_SKIP_EMAILS = {'vijay.raghavan@nestack.co.in', 'rahul@nestack.in', 'vijay@nestack.in'}


def login_if_needed(driver, email, password):
    wait = WebDriverWait(driver, 20)

    driver.get("https://app.apollo.io")

    time.sleep(5)

    # Already logged in
    if "login" not in driver.current_url.lower():
        print(f"[{email}] Already logged in")
        return

    print(f"[{email}] Logging in via Google")

    wait.until(
        EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(., 'Log In with Google')]")
        )
    ).click()

    # Google email
    email_input = wait.until(
        EC.element_to_be_clickable((By.ID, "identifierId"))
    )
    email_input.clear()
    email_input.send_keys(email)
    email_input.send_keys(Keys.ENTER)

    time.sleep(15)

    # Google password
    password_input = wait.until(
        EC.element_to_be_clickable((By.NAME, "Passwd"))
    )
    password_input.clear()
    password_input.send_keys(password)
    password_input.send_keys(Keys.ENTER)

    # Give time for redirects / MFA
    time.sleep(15)
    print('\n\n')
    input("press enter to continue")

    print(f"[{email}] Login complete")
