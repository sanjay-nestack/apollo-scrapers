import os
import sys
# Force UTF-8 stdout/stderr so emoji in print() (✅ ⚠️ ❌) don't crash the whole
# script on Windows cp1252 consoles or when output is redirected/piped (Task Scheduler, .bat > log).
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
from selenium import webdriver

from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import re, time, boto3
import pandas as pd
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import random
from selenium.webdriver.common.action_chains import ActionChains
import shutil
import logging
import subprocess
for h in logging.root.handlers[:]:
    logging.root.removeHandler(h)
# exit(1)
# Configure logging
logging.basicConfig(
    filename=f'app.log', 
    level=logging.INFO,  # Log all messages from DEBUG level and above
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logging.info('File Running Started')

# ========== CONFIGURATION ==========
# Import configuration from config.py
try:
    from config import *
    print("✅ Configuration loaded from config.py")
except ImportError:
    print("⚠️  config.py not found, using default settings")
    # Fallback configuration
    BASE_FOLDER_PATH = os.path.dirname(os.path.abspath(__file__))
    MAX_ROWS_TO_PROCESS = 15
    SLEEP_BETWEEN_ACCOUNTS = 60
    ENABLE_AWS_UPLOAD = False
    AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY', '')
    AWS_SECRET_KEY = os.getenv('AWS_SECRET_KEY', '')
    TARGET_EMAIL = 'madhava.reddy@nestack-tech.com'
    ENABLE_DEBUG_LOGGING = True
    HEADLESS_MODE = False
    MONTHS_TO_INCLUDE = 2

# Validate configuration
try:
    validate_config()
except NameError:
    # validate_config not available, skip validation
    pass

# Legacy variable names for compatibility
access_key = AWS_ACCESS_KEY
secret_key = AWS_SECRET_KEY

# File paths (automatically generated from BASE_FOLDER_PATH)
APOLLO_SEARCH_DATA_CSV = os.path.join(BASE_FOLDER_PATH, 'apollo_search_data.csv')
APOLLO_CREDITS_DATA_CSV = os.path.join(BASE_FOLDER_PATH, 'apollo_credits_only.csv')
APOLLO_UPLOAD_DATA_CSV = os.path.join(BASE_FOLDER_PATH, 'apollo_upload_data_append.csv')

# Ensure base folder exists
os.makedirs(BASE_FOLDER_PATH, exist_ok=True)

print(f"Using base folder: {BASE_FOLDER_PATH}")
print(f"Search data will be saved to: {APOLLO_SEARCH_DATA_CSV}")
print(f"Credits data will be saved to: {APOLLO_CREDITS_DATA_CSV}")
print(f"Upload data will be saved to: {APOLLO_UPLOAD_DATA_CSV}")
print("=" * 60)

def convert_count(c):
    """Convert count string to integer (handles K, M suffixes)"""
    if not c or not isinstance(c, str):
        return 0
    c = c.upper().replace(",", "").strip()
    if not c:
        return 0
    try:
        return int(float(c.replace("K", "")) * 1000) if "K" in c else int(c)
    except:
        return 0

def convert_date(dstr):
    """Convert date string to datetime object"""
    if not dstr or not isinstance(dstr, str):
        return datetime.now()
    # Apollo tooltip format is "Jul 8, 2026, 11:34 AM" (comma before the time).
    for fmt in ("%b %d, %Y, %I:%M %p", "%b %d, %Y %I:%M %p", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(dstr.strip(), fmt)
        except (ValueError, TypeError):
            continue
    return datetime.now()

# def navigate_saved_searches():
#     time.sleep(5)
#     print("entered into function")
#     try:
#         wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
#         driver.get("https://app.apollo.io/#/people")
#     except:
#         driver.get("https://app.apollo.io/#/people")
#     input("press enter to continue")
#     # driver.get("https://app.apollo.io/#/people")
#     # print("driver is re-located")
#     # input("press enter to continue")
#     time.sleep(5)

#     wait.until(EC.visibility_of_element_located((By.LINK_TEXT, "Saved searches"))).click()
#     time.sleep(5)
#     wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Private')]"))).click()
#     time.sleep(5)

from selenium.common.exceptions import TimeoutException

def navigate_saved_searches():
    print("entered into function")

    driver.get("https://app.apollo.io/#/people")

    # try:
    #     wait.until(
    #         EC.visibility_of_element_located((By.LINK_TEXT, "Saved searches"))
    #     )
    # except TimeoutException:
    #     print("Saved searches not found — possible logout or slow load")
    #     return

    # input("press enter to continue")

    # wait.until(
    #     EC.element_to_be_clickable(
    #         (By.XPATH, "//button[contains(text(),'Private')]")
    #     )
    # ).click()


def navigate_saved_searches2():
    time.sleep(5)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
    driver.get("https://app.apollo.io/#/people")
    time.sleep(5)

def get_past_renewal_credit_periods(renewal_date, months=6):
    renewal_dates = []

    # Generate past (months + 1) renewal dates
    for i in range(months, -1, -1):  # e.g., 2 → 1 → 0
        past_date = renewal_date - relativedelta(months=i)
        last_day = (past_date + relativedelta(day=31)).day
        adjusted_day = min(renewal_date.day, last_day)
        past_date = past_date.replace(day=adjusted_day)
        renewal_dates.append(past_date)

    # Create (start, end) periods
    periods = []
    for i in range(months):
        start = renewal_dates[i] + timedelta(days=1)
        end = renewal_dates[i + 1] 
        end = end.replace(hour=start.hour, minute=start.minute)  # preserve time
        periods.append((start, end))

    return periods

def safe_quit(drv):
    """Attempt to quit the webdriver; ignore any errors."""
    try:
        if drv:
            drv.quit()
    except Exception:
        pass

def safe_save_csv(df, file_path, max_retries=3):
    """Safely save DataFrame to CSV with retry logic and backup handling."""
    # Ensure directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    for attempt in range(max_retries):
        try:
            # Try to save directly
            df.to_csv(file_path, index=False)
            print(f"[FILE SAVE] Successfully saved to {file_path}")
            return True
        except PermissionError:
            print(f"[FILE SAVE] Permission denied (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                # Try to create a backup and save to temp file
                try:
                    backup_path = file_path.replace('.csv', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
                    if os.path.exists(file_path):
                        shutil.copy2(file_path, backup_path)
                        print(f"[FILE SAVE] Created backup: {backup_path}")
                    
                    # Try to save to a temp file first
                    temp_path = file_path.replace('.csv', '_temp.csv')
                    df.to_csv(temp_path, index=False)
                    
                    # Then move it to the final location
                    shutil.move(temp_path, file_path)
                    print(f"[FILE SAVE] Successfully saved via temp file to {file_path}")
                    return True
                except Exception as e:
                    print(f"[FILE SAVE] Temp file method failed: {e}")
                    time.sleep(2)  # Wait before retry
            else:
                print(f"[FILE SAVE] All attempts failed. Saving to alternative location...")
                # Save to alternative location
                alt_path = file_path.replace('.csv', f'_alternative_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
                df.to_csv(alt_path, index=False)
                print(f"[FILE SAVE] Saved to alternative location: {alt_path}")
                return True
        except Exception as e:
            print(f"[FILE SAVE] Unexpected error: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                print(f"[FILE SAVE] Failed to save after {max_retries} attempts")
                return False
    return False

def detect_force_logout(drv):
    """Return True if the security logout modal is detected."""
    try:
        body = drv.find_element(By.TAG_NAME, "body").text.lower()
        logout_keywords = [
            "logged out",            # generic
            "logged you out",        # exact phrase in popup
            "security reasons",     # part of the message
            "multiple places",      # part of the message
        ]
        if any(k in body for k in logout_keywords):
            return True
    except Exception:
        pass
    return False

# ---------------------------------------------------------------------------
# Apollo credit-page layout handling
#
# Apollo serves several different credit-page layouts and silently migrates
# accounts between them, so NEVER key off one variant. Captured from live
# accounts (dumps taken 2026-07-16):
#
#   A "credit pool"   /credits/current -> "3963 credits of 4000 credits / mo"
#                                         "Estimated Credit Renewal on: <date>"
#   B "email plan"    /credits/current -> "Email credits usage 9,912 of 10,000 emails / mo"
#                                         "Estimated Credit Renewal on: <date>"
#   C "new donut UI"  /credits/current -> "3,989 of 4,000 credits used"  (donut)
#                                         "Credits will renew on <date>"
#
# Match on TEXT SHAPE and try every known variant, so an account that gets
# migrated keeps working instead of silently recording empty data.
#
# NOTE: the C donut only matches against driver.find_element('body').text -
# BeautifulSoup's get_text() concatenates its number and label without a
# separator ("3,989 of 4,000credits used"), so pass the BODY text here.
# ---------------------------------------------------------------------------
CREDIT_USAGE_PATTERNS = (
    ('A:credits/mo', r'(\d[\d,]*)\s+credits\s+of\s+(\d[\d,]*)\s+credits\s*/\s*mo'),
    ('B:emails/mo', r'Email\s+credits\s+usage\s*(\d[\d,]*)\s+of\s+(\d[\d,]*)\s+emails?\s*/\s*mo'),
    ('C:donut', r'(\d[\d,]*)\s+of\s+(\d[\d,]*)\s+credits\s+used'),
)

RENEWAL_PATTERNS = (
    r'Estimated Credit Renewal on:\s*([A-Za-z]{3} \d{1,2}, \d{4},? \d{1,2}:\d{2} [AP]M)',
    r'Credits will renew on\s*([A-Za-z]{3} \d{1,2}, \d{4},? \d{1,2}:\d{2} [AP]M)',
)

def extract_credit_usage(body_text):
    """Return (used_credits, total_credits) from any known layout, else (0, 0).

    Pass the Selenium body text (not soup text) - see note above."""
    for label, pat in CREDIT_USAGE_PATTERNS:
        m = re.search(pat, body_text or '', re.IGNORECASE)
        if m:
            used = int(m.group(1).replace(',', ''))
            total = int(m.group(2).replace(',', ''))
            print(f'[CREDITS DATA] Layout {label}: used={used} total={total}')
            return used, total
    print('[CREDITS DATA] No known credit-usage layout matched')
    return 0, 0

def extract_renewal_date(body_text, soup_text='', current_url=''):
    """Return the next credit renewal datetime, or None.

    Tries every known layout phrasing against both the body text and the soup
    text, then falls back to deriving it from the URL: Apollo redirects
    /settings/credits/current to ?minDate=<cycle start>&datePreset=current_billing_cycle,
    and the cycle start is the previous renewal, so renewal = minDate + 1 month.
    (Verified: minDate=2026-06-27 -> "Credits will renew on Jul 27, 2026, 9:14 AM".)"""
    for text in (body_text, soup_text):
        if not text:
            continue
        for pat in RENEWAL_PATTERNS:
            m = re.search(pat, text, re.IGNORECASE)
            if not m:
                continue
            raw = m.group(1)
            for fmt in ('%b %d, %Y, %I:%M %p', '%b %d, %Y %I:%M %p'):
                try:
                    return datetime.strptime(raw, fmt)
                except ValueError:
                    continue

    # Fallback: derive from the billing-cycle start in the URL.
    m = re.search(r'minDate=(\d{4}-\d{2}-\d{2})', current_url or '')
    if m:
        try:
            derived = datetime.strptime(m.group(1), '%Y-%m-%d') + relativedelta(months=1)
            print(f'[CREDITS DATA] Renewal text not found - derived {derived:%Y-%m-%d} '
                  f'from URL minDate={m.group(1)}')
            logging.info(f'Renewal date derived from URL minDate={m.group(1)} -> {derived:%Y-%m-%d}')
            return derived
        except ValueError:
            pass
    return None

def detect_cloudflare_challenge(drv):
    """Return True if a Cloudflare 'Verify you are human' widget is on the page.

    This must be checked explicitly: the challenge renders as an overlay and the
    page text behind it still parses, so a missing field is NOT a reliable signal
    that we were challenged (and vice versa)."""
    try:
        # Turnstile renders inside an iframe served from challenges.cloudflare.com.
        if drv.find_elements(By.CSS_SELECTOR, "iframe[src*='challenges.cloudflare.com']"):
            return True
        body = drv.find_element(By.TAG_NAME, "body").text.lower()
        cf_keywords = [
            "verify you are human",
            "checking your browser",
            "needs to review the security of your connection",
        ]
        if any(k in body for k in cf_keywords):
            return True
    except Exception:
        pass
    return False

def clear_cloudflare_challenge(drv, max_reloads=3, settle=6):
    """Reload the page until the Cloudflare challenge clears.

    The challenge is transient - a plain refresh drops it in practice. Left
    unhandled it blocks the credit chart from rendering, which is what silently
    produced rows with a renewal date but all six months empty.

    Returns True if the page ended up clean (or was never challenged)."""
    for attempt in range(max_reloads):
        if not detect_cloudflare_challenge(drv):
            return True
        print(f"[CLOUDFLARE] Challenge detected - reloading ({attempt + 1}/{max_reloads})")
        logging.info(f"Cloudflare challenge detected - reload attempt {attempt + 1}")
        try:
            drv.refresh()
        except Exception as e:
            print(f"[CLOUDFLARE] Refresh failed: {e}")
            return False
        time.sleep(settle + random.uniform(0, 2))

    if detect_cloudflare_challenge(drv):
        print(f"[CLOUDFLARE] Challenge still present after {max_reloads} reloads")
        logging.info(f"Cloudflare challenge persisted after {max_reloads} reloads")
        return False
    return True

def cleanup_chrome_processes():
    """Kill any existing Chrome processes to avoid conflicts.
    IMPORTANT: This only kills running processes, it does NOT delete profile directories or sessions."""
    try:
        if os.name == 'nt':  # Windows
            # Kill processes multiple times to ensure they're terminated
            for attempt in range(3):
                try:
                    subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'], 
                                 capture_output=True, timeout=10)
                    subprocess.run(['taskkill', '/F', '/IM', 'chromedriver.exe'], 
                                 capture_output=True, timeout=10)
                except:
                    pass
                time.sleep(2)  # Wait between attempts
            
            # Additional cleanup: kill any remaining Chrome processes by PID
            try:
                # Get all Chrome PIDs and kill them
                result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq chrome.exe', '/FO', 'CSV'], 
                                     capture_output=True, text=True, timeout=5)
                if 'chrome.exe' in result.stdout:
                    subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'], 
                                 capture_output=True, timeout=10)
            except:
                pass
                
        else:  # Linux/Mac
            subprocess.run(['pkill', '-9', '-f', 'chrome'], 
                         capture_output=True, timeout=5)
            subprocess.run(['pkill', '-9', '-f', 'chromedriver'], 
                         capture_output=True, timeout=5)
        
        # Wait longer for processes to fully terminate and release file handles
        time.sleep(5)
    except Exception as e:
        print(f"[CLEANUP] Warning: Could not cleanup Chrome processes: {e}")

def remove_chrome_lock_files(profile_dir, max_retries=5):
    """Remove Chrome lock files from profile directory.
    These are just lock files, NOT session data. Removing them is safe and necessary
    when Chrome crashes and leaves stale lock files behind.
    Retries multiple times to handle files locked by terminating processes."""
    lock_files = [
        'SingletonLock',      # Windows lock file
        'lockfile',            # Linux lock file
        'SingletonSocket',     # Windows socket lock
        'SingletonCookie',     # Windows cookie lock
    ]
    
    removed_count = 0
    
    def try_remove_file(lock_path, lock_file_name):
        """Try to remove a lock file with retries."""
        for attempt in range(max_retries):
            try:
                if os.path.exists(lock_path):
                    # On Windows, try to unlock the file first
                    if os.name == 'nt' and attempt > 0:
                        # Try to close any handles to the file using handle.exe (if available)
                        # or just wait longer
                        time.sleep(2 * (attempt + 1))  # Exponential backoff
                    
                    os.remove(lock_path)
                    print(f"[CLEANUP] Removed lock file: {lock_file_name}")
                    return True
            except PermissionError as e:
                if attempt < max_retries - 1:
                    print(f"[CLEANUP] Lock file {lock_file_name} is locked, retrying in {2 * (attempt + 1)} seconds... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(2 * (attempt + 1))  # Wait longer on each retry
                else:
                    print(f"[CLEANUP] Warning: Could not remove lock file {lock_file_name} after {max_retries} attempts: {e}")
                    # Try one more aggressive cleanup
                    try:
                        cleanup_chrome_processes()
                        time.sleep(3)
                        os.remove(lock_path)
                        print(f"[CLEANUP] Successfully removed {lock_file_name} after aggressive cleanup")
                        return True
                    except:
                        print(f"[CLEANUP] Final attempt failed for {lock_file_name}")
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(1)
                else:
                    print(f"[CLEANUP] Warning: Could not remove lock file {lock_file_name}: {e}")
        return False
    
    # Remove lock files from main profile directory
    for lock_file in lock_files:
        lock_path = os.path.join(profile_dir, lock_file)
        if try_remove_file(lock_path, lock_file):
            removed_count += 1
    
    # Also check for lock files in Default subdirectory
    default_dir = os.path.join(profile_dir, 'Default')
    if os.path.exists(default_dir):
        for lock_file in lock_files:
            lock_path = os.path.join(default_dir, lock_file)
            if try_remove_file(lock_path, f"Default/{lock_file}"):
                removed_count += 1
    
    if removed_count > 0:
        print(f"[CLEANUP] Removed {removed_count} lock file(s) from profile directory")
    
    return removed_count

def cleanup_apollo_chrome():
    """Kill ONLY orphaned Chrome/chromedriver processes bound to the Selenium
    apollo profiles (C:\\selenium\\apollo_profiles). The user's personal Chrome
    (default profile) is left untouched.

    Orphans left behind by previous crashed/killed runs hold the profile lock and
    cause 'ProcessSingleton ... Error code: 32' and 'Opening in existing browser
    session' -> 'Chrome instance exited' failures on the next launch."""
    if os.name != 'nt':
        # Best-effort on POSIX: match the profiles path in the process args.
        try:
            subprocess.run(['pkill', '-9', '-f', 'apollo_profiles'], capture_output=True, timeout=10)
        except Exception:
            pass
        return
    ps_cmd = (
        "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe' or Name='chromedriver.exe'\" | "
        "Where-Object { $_.CommandLine -like '*selenium\\apollo_profiles*' -or $_.Name -eq 'chromedriver.exe' } | "
        "ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch {} }"
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd],
                       capture_output=True, timeout=30)
        time.sleep(2)  # let handles release
    except Exception as e:
        print(f"[CLEANUP] Apollo chrome cleanup warning: {e}")

def start_driver(email, max_retries=3):
    """Start Chrome driver with unique profile directory to avoid conflicts.
    Preserves existing sessions by using original profile naming convention."""
    profile_base = r"C:\selenium\apollo_profiles"
    
    # IMPORTANT: Preserve original naming convention to maintain existing sessions
    # Only replace @ with _ (NOT dots) - this matches the original code
    # Example: user.name@domain.com -> user.name_domain.com (preserves dots)
    original_profile_dir = os.path.join(profile_base, email.replace("@", "_"))
    
    # Check if original profile exists (backward compatibility)
    if os.path.exists(original_profile_dir) and os.path.isdir(original_profile_dir):
        profile_dir = original_profile_dir
        print(f"[DRIVER] Using existing profile directory: {profile_dir}")
    else:
        # If original doesn't exist, check for new naming (in case it was created)
        safe_email = email.replace("@", "_").replace(".", "_")
        new_profile_dir = os.path.join(profile_base, safe_email)
        if os.path.exists(new_profile_dir) and os.path.isdir(new_profile_dir):
            profile_dir = new_profile_dir
            print(f"[DRIVER] Using existing profile directory (new naming): {profile_dir}")
        else:
            # Use original naming for new profiles to maintain consistency
            profile_dir = original_profile_dir
            print(f"[DRIVER] Creating new profile directory: {profile_dir}")
    
    # Cleanup ORPHANED scraper Chrome from previous runs before starting.
    # Targeted at apollo profiles only, so the user's personal Chrome is left alone.
    # This does NOT delete profile directories / sessions.
    print(f"[DRIVER] Cleaning up orphaned scraper Chrome processes...")
    cleanup_apollo_chrome()

    # Remove stale lock files from profile directory
    # These are just lock files, NOT session data - safe to remove
    print(f"[DRIVER] Removing lock files from profile directory...")
    remove_chrome_lock_files(profile_dir)
    
    # Wait longer to ensure processes are fully terminated and files are released
    print(f"[DRIVER] Waiting for processes to fully terminate...")
    time.sleep(3)
    
    # Ensure profile directory exists (won't overwrite existing sessions)
    os.makedirs(profile_dir, exist_ok=True)
    
    for attempt in range(max_retries):
        try:
            options = webdriver.ChromeOptions()

            # ---- Persistent profile (KEY PART) ----
            options.add_argument(f"--user-data-dir={profile_dir}")

            # ---- Stealth tweaks (SAFE) ----
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-infobars")

            # ---- Realistic UA ----
            options.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/118.0.0.0 Safari/537.36"
            )

            print(f"[DRIVER] Attempting to start driver for {email} (attempt {attempt + 1}/{max_retries})...")
            print(f"[DRIVER] Profile directory: {profile_dir}")
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=options
            )

            # Hide webdriver flag (post-launch)
            driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            
            print(f"[DRIVER] Driver started successfully for {email}")
            return driver
            
        except Exception as e:
            print(f"[DRIVER] Attempt {attempt + 1} failed for {email}: {e}")
            if attempt < max_retries - 1:
                print(f"[DRIVER] Performing cleanup before retry {attempt + 2}...")
                # Kill the orphaned/failed scraper Chrome for this profile, then clear locks.
                cleanup_apollo_chrome()
                # Remove any lock files that might have been created during failed attempt
                remove_chrome_lock_files(profile_dir)
                # Wait longer after cleanup to ensure everything is released
                wait_time = 8 + (attempt * 2)  # Increase wait time with each retry
                print(f"[DRIVER] Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
            else:
                print(f"[DRIVER] All {max_retries} attempts failed for {email}")
                raise
    
    return None

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

# https://docs.google.com/spreadsheets/d/1kKqEfKLSW9cUtcjmNlinxeYXt-EtcXm5B5c4m7_CnbI/edit?pli=1&gid=0#gid=0
# sheet_url = "https://docs.google.com/spreadsheets/d/1kKqEfKLSW9cUtcjmNlinxeYXt-EtcXm5B5c4m7_CnbI/export?format=csv&gid=0"
# df = pd.read_csv(sheet_url)
df = pd.read_csv(os.path.join(BASE_FOLDER_PATH, 'ApolloUsers.csv'))
df = df.iloc[::-1]


columns_apollo_search = [
    'email',
    'status',
    'last_execution',
    'used_credits',
    'total_credits',
    'renews_on',
    'saved_titles',
    'saved_counts',
    'total_saved',
    'netnew_counts',
    'total_netnew',
    # The search block writes failed_reason on error, so this column exists in the
    # CSV. It MUST be listed here: read_csv(names=..., header=None) with fewer names
    # than columns silently promotes the first column to the index, which made
    # apollo_search_data['email'] return status values - so the email was never found
    # and condition1 was always False for every account.
    'failed_reason'
    ]
if os.path.exists(APOLLO_SEARCH_DATA_CSV):
    apollo_search_data = pd.read_csv(
        APOLLO_SEARCH_DATA_CSV,
        names=columns_apollo_search,
        header=None,  # tells pandas the file has no header row
    )
else:
    apollo_search_data = pd.DataFrame(columns=columns_apollo_search)

columns_apollo_credits = [
    'email',
    'status',
    'last_execution',
    'renewal_date',
    'first_month_credits',
    'second_month_credits',
    'third_month_credits',
    'fourth_month_credits',
    'fifth_month_credits',
    'sixth_month_credits',
    'first_month_provided',
    'second_month_provided',
    'third_month_provided',
    'fourth_month_provided',
    'fifth_month_provided',
    'sixth_month_provided'
    ]
if os.path.exists(APOLLO_CREDITS_DATA_CSV):
    apollo_credits_data = pd.read_csv(
        APOLLO_CREDITS_DATA_CSV,
        names=columns_apollo_credits,
        header=None,  # tells pandas the file has no header row
    )
else:
    apollo_credits_data = pd.DataFrame(columns=columns_apollo_credits)

columns_apollo_upload = [
    'email',
    'data_count',
    'last_uploaded',
    'status',
    'last_execution',
    'monthly_breakdown'
]
if os.path.exists(APOLLO_UPLOAD_DATA_CSV):
    apollo_upload_data = pd.read_csv(
        APOLLO_UPLOAD_DATA_CSV,
        names=columns_apollo_upload,
        header=None,  # tells pandas the file has no header row
    )
else:
    apollo_upload_data = pd.DataFrame(columns=columns_apollo_upload)

apollo_upload_details = []
apollo_credits_data['renewal_date'] = pd.to_datetime(apollo_credits_data['renewal_date'], errors='coerce', format='%Y-%m-%d %H:%M:%S')
final_df = pd.merge(df, apollo_credits_data, left_on='Email', right_on='email', how='left')

final_df_sorted = final_df.sort_values(by='renewal_date', ascending=True)
# input("press input to continue")

# ONE-TIME STARTUP CLEANUP:
# On this machine, launching the scraper's Chrome while ANY Chrome is already
# running makes the new process hand off to the existing browser session and exit
# ("session not created: Chrome failed to start: crashed"). So close ALL Chrome
# (including the personal browser) once, up front, for reliable launches.
# IMPORTANT: do NOT open Chrome again while the run is in progress.
print("=" * 60)
print("[STARTUP] Closing ALL Chrome windows so the scraper can launch cleanly.")
print("[STARTUP] This also closes your personal Chrome. Do NOT reopen Chrome during the run.")
print("=" * 60)
logging.info("[STARTUP] Closing all Chrome before run (auto-close-all mode)")
cleanup_chrome_processes()

email_number = 1
for index, row in final_df_sorted.iterrows():
    email = row["Email"]
    password = row["2026 june Password"]
    logging.info(f'Index: {email_number} - Running for {email}')
    email_number += 1

    # if TARGET_EMAIL and email.lower().strip() not in [s_email.lower().strip() for s_email in TARGET_EMAIL]:
    #     print(f"Skipping {email} as it is not {TARGET_EMAIL}")
    #     continue
    # if (row['renewal_date'] is not None) and (row['renewal_date'] > (datetime.now() + timedelta(days=10))):
    #     print(f"{email} - Renewal date is more than 10 days from now. Skipping.")
    #     continue
    if email.lower().strip() in ['vijay.raghavan@nestack.co.in', 'rahul@nestack.in', 'vijay@nestack.in']:
        continue


    # If apollo_search_data is not empty and email exists
    hours_to_check = 22
    condition1 = False
    print(f'[CONDITION CHECK] Checking condition1 for {email}...')
    print(f'[CONDITION CHECK] apollo_search_data empty: {apollo_search_data.empty}')
    if not apollo_search_data.empty:
        print(f'[CONDITION CHECK] Email in apollo_search_data: {email in apollo_search_data["email"].values}')
    if not apollo_search_data.empty and email in apollo_search_data['email'].values:
        existing_row = apollo_search_data[apollo_search_data['email'] == email].iloc[0]
        print(f'[CONDITION CHECK] Found existing row - status: {existing_row["status"]}, last_execution: {existing_row["last_execution"]}')
        
        # Check if data is actually valid (not empty/failed)
        saved_titles = existing_row.get('saved_titles', '')
        saved_counts = existing_row.get('saved_counts', '')
        total_saved = existing_row.get('total_saved', 0)
        
        # Check if saved_titles is empty or just contains empty strings
        has_valid_titles = False
        if saved_titles and str(saved_titles).strip() and str(saved_titles) not in ['', 'nan', 'None']:
            # Check if it's not just an empty tuple representation
            if not (str(saved_titles).strip().startswith("('')") or str(saved_titles).strip() == "('',)"):
                has_valid_titles = True
        
        # Check if total_saved is meaningful (greater than 0)
        has_valid_data = False
        try:
            total_saved_val = float(total_saved) if total_saved else 0
            if total_saved_val > 0:
                has_valid_data = True
        except:
            pass
        
        print(f'[CONDITION CHECK] Data validation - saved_titles: "{saved_titles}", total_saved: {total_saved}')
        print(f'[CONDITION CHECK] Has valid titles: {has_valid_titles}, Has valid data (total_saved > 0): {has_valid_data}')
        
        time_diff = datetime.now() - pd.to_datetime(existing_row['last_execution'])
        print(f'[CONDITION CHECK] Time since last execution: {time_diff.total_seconds() / 3600:.2f} hours (threshold: {hours_to_check} hours)')
        
        # Only skip if: status is completed AND within time threshold AND has valid data
        if (existing_row['status'] == 'completed') and (pd.to_datetime(existing_row['last_execution']) > (datetime.now() - timedelta(hours=hours_to_check))):
            if has_valid_titles or has_valid_data:
                logging.info(f'Last execution was on {existing_row['last_execution']} for email {email} and current time is {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}')
                logging.info(f"Skipping {email} as it already exists in apollo_search_data with 'completed' status and valid data")
                print(f'[CONDITION CHECK] Last execution was on {existing_row['last_execution']} for email {email} and current time is {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}')
                print(f'[CONDITION CHECK] Skipping {email} - status is "completed" with valid data')
                condition1 = True
            else:
                print(f'[CONDITION CHECK] ⚠️  Status is "completed" but data is empty/invalid - will reprocess')
                print(f'[CONDITION CHECK] Previous run appears to have failed despite "completed" status')
                condition1 = False
        else:
            print(f'[CONDITION CHECK] Not skipping - status: {existing_row["status"]} or time check failed')
    else:
        print(f'[CONDITION CHECK] Email not found in apollo_search_data or data is empty, condition1 remains False')

    condition2 = False
    if not apollo_credits_data.empty and email in apollo_credits_data['email'].values:
        existing_row = apollo_credits_data[apollo_credits_data['email'] == email].iloc[0]
        
        # Check if credits data is actually valid
        first_month_credits = existing_row.get('first_month_credits', 0)
        renewal_date = existing_row.get('renewal_date', '')
        
        has_valid_credits = False
        try:
            # Don't test `if first_month_credits` - 0.0 is falsy but is a real value
            # (a fresh account genuinely can have 0 credits used), which would make a
            # legitimate zero row look invalid and reprocess on every run.
            if pd.notna(first_month_credits) and str(first_month_credits) not in ['', 'nan', 'None', '-1']:
                first_month_val = float(first_month_credits)
                if first_month_val >= 0:  # Valid if >= 0 (0 is also valid)
                    has_valid_credits = True
        except:
            pass
        
        has_valid_renewal = renewal_date and str(renewal_date) not in ['', 'nan', 'None']
        
        print(f'[CONDITION CHECK] Credits data validation - first_month_credits: {first_month_credits}, renewal_date: {renewal_date}')
        print(f'[CONDITION CHECK] Has valid credits: {has_valid_credits}, Has valid renewal: {has_valid_renewal}')
        
        if (existing_row['status'] == 'completed') and (pd.to_datetime(existing_row['last_execution']) > (datetime.now() - timedelta(hours=hours_to_check))):
            # BOTH must be present. With `or`, a row that had a renewal_date but no
            # month values at all counted as "valid" and was skipped, so the empty
            # data stuck for hours_to_check and the 'will reprocess' branch below
            # could never fire for the exact rows it was written to catch.
            if has_valid_credits and has_valid_renewal:
                print(f"[CONDITION CHECK] Skipping {email} as it already exists in apollo_credits_data with 'completed' status and valid data")
                logging.info(f"Skipping {email} as it already exists in apollo_credits_data with 'completed' status")
                condition2 = True
            else:
                print(f'[CONDITION CHECK] ⚠️  Credits status is "completed" but data is invalid - will reprocess')
                condition2 = False
        else:
            condition2 = False

    condition3 = False
    if not apollo_upload_data.empty and email in apollo_upload_data['email'].values:
        existing_row = apollo_upload_data[apollo_upload_data['email'] == email].iloc[0]
        
        # Check if upload data is actually valid
        data_count = existing_row.get('data_count', 0)
        monthly_breakdown = existing_row.get('monthly_breakdown', '')
        
        has_valid_count = False
        try:
            if data_count and str(data_count) not in ['', 'nan', 'None']:
                count_val = float(data_count)
                if count_val > 0:
                    has_valid_count = True
        except:
            pass
        
        has_valid_breakdown = monthly_breakdown and str(monthly_breakdown) not in ['', 'nan', 'None', '[]']
        
        print(f'[CONDITION CHECK] Upload data validation - data_count: {data_count}, monthly_breakdown: {str(monthly_breakdown)[:50]}...')
        print(f'[CONDITION CHECK] Has valid count: {has_valid_count}, Has valid breakdown: {has_valid_breakdown}')
        
        if (existing_row['status'] == 'completed') and (pd.to_datetime(existing_row['last_execution']) > (datetime.now() - timedelta(hours=hours_to_check))):
            if has_valid_count or has_valid_breakdown:
                print(f"[CONDITION CHECK] Skipping {email} as it already exists in apollo_upload_data with 'completed' status and valid data")
                logging.info(f"Skipping {email} as it already exists in apollo_upload_data with 'completed' status")
                condition3 = True
            else:
                print(f'[CONDITION CHECK] ⚠️  Upload status is "completed" but data is invalid - will reprocess')
                condition3 = False
        else:
            condition3 = False


    condition4 = True

    rd = row.get('renewal_date')
    fm = row.get('first_month_credits')

    # Parse first_month robustly
    def to_int(x, default=0):
        try:
            return int(x)
        except (TypeError, ValueError):
            return default

    first_month_count = to_int(fm, 0)

    # Only proceed if rd is a datetime
    if isinstance(rd, datetime):
        window = timedelta(hours=12)
        # Use the same tz as rd (if aware); otherwise naive now()
        now = datetime.now()
        in_window = (rd - window) <= now <= (rd + window)

        # If we're within ±12h of renewal AND first_month_count < 9700 -> condition4 becomes False
        if in_window and (first_month_count < 9700):
            condition4 = False

    # Must include condition1, or an account whose credits+upload are fresh gets
    # skipped entirely and its search data never refreshes - which is what the
    # message already claims ("all three tables"). This was masked while the
    # columns_apollo_search mismatch above pinned condition1 to False.
    if (condition2 and condition3) :
        print(f"Skipping {email} as it already exists in all three tables with 'completed' status")
        logging.info(f"Skipping {email} as it already exists in all three tables with 'completed' status")
        continue
    # combined_condition = condition1 or condition2 or condition3

    apollo_search_field = {
        'email': email,
        'status': 'failed',
        'last_execution': None,
        'used_credits': 0,
        'total_credits': 0,
        'renews_on': None,
        'saved_titles': None,
        'saved_counts': None,
        'total_saved': None,
        'netnew_counts': None,
        'total_netnew': None
    }

    emails_data = []
    status = 'failed'
    apollo_credits_field = {
        'email': email,
        'status': status,
        'last_execution': '',
        'renewal_date': '',
        'first_month_credits': 0,
        'second_month_credits': 0,
        'third_month_credits': 0,
        'fourth_month_credits': 0,
        'fifth_month_credits': 0,
        'sixth_month_credits': 0,
        'first_month_provided': 0,
        'second_month_provided': 0,
        'third_month_provided': 0,
        'fourth_month_provided': 0,
        'fifth_month_provided': 0,
        'sixth_month_provided': 0
    }
    apollo_upload_filed = {
        'email': email,
        'data' : [],
        'status': 'failed',
        'last_execution': ''
    }
    
    driver = None
    data = []
    try:
        driver = start_driver(email)
        
        if driver is None:
            raise Exception("Failed to initialize driver after all retries")
        
        login_if_needed(driver, email, password)

        # ---- Your target page ----
        driver.get("https://app.apollo.io/#/settings/credits/current")
        time.sleep(10)

        # The search block below reads this page's text for credits/renewal, and the
        # logout check right after matches on "log in" - a Cloudflare challenge can
        # trip both. Clear it before either runs.
        clear_cloudflare_challenge(driver)

        body_txt = driver.find_element(By.TAG_NAME, "body").text.lower()
        logout_keywords = [
            "logged out",
            "security reasons",
            "log in",
            "multiple places",
        ]

        if any(k in body_txt for k in logout_keywords):
            raise Exception("Apollo forced logout detected")

        print(f"[{email}] Page loaded successfully")
    except Exception as e:
        print(f"[INIT] ERROR during driver initialization or page load: {e}")
        print(f"[INIT] Exception type: {type(e).__name__}")
        import traceback
        print(f"[INIT] Full traceback:\n{traceback.format_exc()}")
        
        # Check if driver was successfully created before checking for logout
        if driver:
            try:
                if detect_force_logout(driver):
                    print("[INIT] Forced logout detected - closing driver")
                    safe_quit(driver)
                    time.sleep(10)
                    cleanup_chrome_processes()
                    time.sleep(20)
                    continue
            except Exception as logout_check_error:
                print(f"[INIT] Error checking for logout: {logout_check_error}")
        
        # If driver initialization failed, cleanup and skip
        if driver is None:
            print("[INIT] Driver initialization failed - cleaning up and skipping")
            cleanup_chrome_processes()
            time.sleep(10)
            continue
        
        # If driver exists but other error occurred, keep it open
        print("[INIT] Error is not a forced logout - driver will remain open")
        print("[INIT] Continuing with next sections...")
        # Don't quit driver - let it continue to next sections
    if driver:
        print('Driver is started')
        wait = WebDriverWait(driver, 20)
    
    print(f'[CONDITION CHECK] Condition1: {condition1}, Condition2: {condition2}, Condition3: {condition3}')
    print(f'[CONDITION CHECK] Will process search data: {not condition1}')
    print(f'[CONDITION CHECK] Will process credits data: {not condition2}')
    print(f'[CONDITION CHECK] Will process upload data: {not condition3}')
    
    # Check if all conditions are True (all sections will be skipped)
    if condition1 and condition2 and condition3:
        print(f'[CONDITION CHECK] ⚠️  WARNING: All processing sections will be skipped!')
        print(f'[CONDITION CHECK] Email was processed recently (within {hours_to_check} hours)')
        print(f'[CONDITION CHECK] Driver will be closed since there is nothing to process')
        print(f'[CONDITION CHECK] To force processing, you can:')
        print(f'[CONDITION CHECK]   1. Wait {hours_to_check} hours since last execution')
        print(f'[CONDITION CHECK]   2. Delete the email entry from CSV files')
        print(f'[CONDITION CHECK]   3. Modify the hours_to_check threshold')
    
    # condition2 keeps its computed value: credits run ONLY if the existing credits
    # data is older than hours_to_check (or missing/invalid). No force-run override.
    
    if not True:
        condition2 = False
        condition3 = False
        print(f'[SEARCH DATA] Starting search data extraction for {email}')
        print(f'[SEARCH DATA] Condition1: {condition1}, Condition2: {condition2}')
        print(f'[SEARCH DATA] Driver status: {"Valid" if driver else "None/Invalid"}')
        
        try:
            # Wrap the entire search data extraction in try-catch to prevent driver from closing
            try:
                print(f'[SEARCH DATA] Getting page text from driver...')
                if driver is None:
                    raise Exception("Driver is None - cannot proceed")
                print(f'[SEARCH DATA] Current URL: {driver.current_url if driver else "N/A"}')
                page_text = driver.find_element(By.TAG_NAME, 'body').text
                print(f'[SEARCH DATA] Page text retrieved, length: {len(page_text)} characters')
            except Exception as page_error:
                print(f'[SEARCH DATA] ERROR getting page text: {page_error}')
                print(f'[SEARCH DATA] Driver will remain open, continuing with next section...')
                raise  # Re-raise to be caught by outer try-catch

            # Use the same layout-agnostic extraction as the credits section. This block
            # used to carry its own copy of the old single-layout regexes, which is why
            # nearly every apollo_search_data row has used_credits=0 / total_credits=0
            # and an empty renews_on: those accounts are simply on a layout the old
            # pattern never matched. page_text is body text, which the donut needs.
            used_credits, total_credits = extract_credit_usage(page_text)
            renewal_date = extract_renewal_date(
                body_text=page_text,
                current_url=driver.current_url,
            )
            print(f'[SEARCH DATA] used={used_credits} total={total_credits} renews_on={renewal_date}')
            try:
                print('[SAVED SEARCHES] Trying to navigate for save')
                if driver is None:
                    raise Exception("Driver is None - cannot navigate")
                print(f'[SAVED SEARCHES] Current URL: {driver.current_url}')
                try:
                    navigate_saved_searches()
                    print(f"[SAVED SEARCHES] Navigated successfully, current URL: {driver.current_url}")
                except Exception as nav_error:
                    print(f'[SAVED SEARCHES] ERROR during navigation: {nav_error}')
                    print(f'[SAVED SEARCHES] Driver will remain open, continuing...')
                    raise

                titles = []
                try:
                    print(f"[SAVED SEARCHES] Looking for pinned icon elements...")
                    if driver is None:
                        raise Exception("Driver is None - cannot find elements")
                    icon_elements = driver.find_elements(By.XPATH, "//i[contains(@class, 'mdi-pin')]")
                    print(f"[SAVED SEARCHES] Found {len(icon_elements)} icon elements")
                except Exception as find_error:
                    print(f'[SAVED SEARCHES] ERROR finding icon elements: {find_error}')
                    print(f'[SAVED SEARCHES] Driver will remain open, continuing with empty titles list...')
                    icon_elements = []

                for idx, element in enumerate(icon_elements):
                    try:
                        print(f"[SAVED SEARCHES] Processing icon element {idx + 1}/{len(icon_elements)}")
                        parent = element.find_element(By.XPATH, "..")
                        grandparent = parent.find_element(By.XPATH, "..").find_element(By.XPATH, "..").get_attribute("outerHTML")
                        soup = BeautifulSoup(grandparent, "html.parser")
                        icon_element = soup.find("i", class_="mdi")
                        if icon_element and "mdi-pin" in icon_element.get("class", []):
                            parent_element = icon_element.parent
                            adjacent_span = parent_element.find_next("span")
                            if adjacent_span:
                                adjacent_text = adjacent_span.get_text(strip=True)
                                titles.append(adjacent_text)
                                print(f"[SAVED SEARCHES] Added title: {adjacent_text}")
                    except Exception as e:
                        print(f"[SAVED SEARCHES] Error processing icon element {idx + 1}: {e}")

                print(f"[SAVED SEARCHES] Total titles found: {len(titles)}")
                if len(titles) == 0:
                    print("[SAVED SEARCHES] WARNING: No pinned titles found! Titles list is empty.")
                    print("[SAVED SEARCHES] This might mean:")
                    print("[SAVED SEARCHES]   1. No pinned searches exist")
                    print("[SAVED SEARCHES]   2. Page structure changed")
                    print("[SAVED SEARCHES]   3. Browser window closed or page not loaded correctly")
                    print(f"[SAVED SEARCHES] Current URL: {driver.current_url if driver else 'Driver is None'}")
                    print(f"[SAVED SEARCHES] Driver window handles: {len(driver.window_handles) if driver else 0}")
                    print("[SAVED SEARCHES] Triggering fallback method (views dropdown)...")
                    # Raise exception to trigger fallback method immediately
                    raise Exception("No pinned elements found - triggering fallback method (views dropdown)")
                
                searches = dict()
                netnew = dict()
                print(f"[SAVED SEARCHES] going for net new - will process {len(titles)} titles")
                
                # Process titles if we have any
                if len(titles) > 0:
                    for title_idx, title in enumerate(titles):
                        print(f"[SAVED SEARCHES] Processing title {title_idx + 1}/{len(titles)}: '{title}'")
                        # Check if driver is still valid
                        try:
                            if driver is None:
                                print("[SAVED SEARCHES] ERROR: Driver is None! Cannot continue.")
                                break
                            # Check if browser window is still open
                            driver.current_url
                            print(f"[SAVED SEARCHES] Driver is valid, current URL: {driver.current_url}")
                        except Exception as driver_check_error:
                            print(f"[SAVED SEARCHES] ERROR: Driver is no longer valid: {driver_check_error}")
                            print("[SAVED SEARCHES] Browser may have closed unexpectedly")
                            break
                        
                        try:
                            print(f"[SAVED SEARCHES] Initializing search dicts for '{title}'")
                            searches[title] = 0
                            netnew[title] = 0
                            xpath_expression = f"(//span[contains(., '{title}')])[1]"
                            print(f"[SAVED SEARCHES] Waiting for element with XPath: {xpath_expression}")
                            try:
                                if driver is None or wait is None:
                                    raise Exception("Driver or wait is None")
                                title_div = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_expression)))
                                print(f"[SAVED SEARCHES] Element found, clicking on '{title}'")
                                title_div.click()
                                print(f"[SAVED SEARCHES] Clicked on '{title}', waiting 2 seconds...")
                                time.sleep(2)
                            except Exception as click_error:
                                print(f'[SAVED SEARCHES] ERROR clicking on title "{title}": {click_error}')
                                print(f'[SAVED SEARCHES] Skipping this title, driver remains open...')
                                continue  # Skip to next title instead of breaking

                            print(f"[SAVED SEARCHES] Looking for saved links after clicking '{title}'")
                            try:
                                if driver is None:
                                    raise Exception("Driver is None")
                                saved_links = driver.find_elements(By.XPATH, "//a[contains(@class, 'zp-link')]")
                                print(f"[SAVED SEARCHES] Found {len(saved_links)} saved links")
                            except Exception as link_error:
                                print(f'[SAVED SEARCHES] ERROR finding saved links: {link_error}')
                                print(f'[SAVED SEARCHES] Continuing with empty links list...')
                                saved_links = []
                            for link_idx, link in enumerate(saved_links):
                                if "Saved" in link.text:
                                    adjacent_text = link.text.replace("Saved", "").strip()
                                    if "(" in adjacent_text and ")" in adjacent_text:
                                        saved_count = adjacent_text.lstrip("(").rstrip(")").strip()
                                        if saved_count[-1].lower() == "k":
                                            saved_count = float(saved_count[:-1]) * 1000
                                        else:
                                            saved_count = float(saved_count)
                                        searches[title] = saved_count
                                if "Net New" in link.text:
                                    adjacent_text = link.text.replace("Net New", "").strip()
                                    if "(" in adjacent_text and ")" in adjacent_text:
                                        netnew_count = adjacent_text.lstrip("(").rstrip(")").strip()
                                        if netnew_count[-1].lower() == "k":
                                            netnew_count = float(netnew_count[:-1]) * 1000
                                        elif netnew_count[-1].lower() == "m":
                                            netnew_count = float(netnew_count[:-1]) * 1000000
                                        else:
                                            netnew_count = float(netnew_count)
                                        netnew[title] = netnew_count
                                        print(f"[SAVED SEARCHES] Found Net New count for '{title}': {netnew_count}")
                            print(f"[SAVED SEARCHES] Completed processing '{title}', navigating back...")
                            try:
                                navigate_saved_searches()
                                print(f"[SAVED SEARCHES] Navigation complete for '{title}'")
                            except Exception as nav_back_error:
                                print(f'[SAVED SEARCHES] ERROR navigating back: {nav_back_error}')
                                print(f'[SAVED SEARCHES] Driver remains open, continuing...')
                        except Exception as e:
                            print(f"[SAVED SEARCHES] ERROR processing title '{title}': {e}")
                            print(f"[SAVED SEARCHES] Exception type: {type(e).__name__}")
                            import traceback
                            print(f"[SAVED SEARCHES] Traceback: {traceback.format_exc()}")
                            # update_tracker_failed(email, 'failed')
                            apollo_credits_data['status'] = 'failed'
                            apollo_search_field['failed_reason'] = str(e)
                            print(f"[SAVED SEARCHES] Attempting to navigate back after error...")
                            try:
                                if driver is not None:
                                    navigate_saved_searches()
                                    print(f"[SAVED SEARCHES] Navigation complete after error")
                            except Exception as nav_error:
                                print(f'[SAVED SEARCHES] ERROR during error recovery navigation: {nav_error}')
                                print(f'[SAVED SEARCHES] Driver remains open, continuing...')
                
                if len(titles) == 0:
                    print("[SAVED SEARCHES] No titles were processed, searches and netnew dicts remain empty")
            except Exception as e:
                print(f"[SAVED SEARCHES] Outer exception caught: {e}")
                print(f"[SAVED SEARCHES] Exception type: {type(e).__name__}")
                import traceback
                print(f"[SAVED SEARCHES] Full traceback: {traceback.format_exc()}")
                print(f"[SAVED SEARCHES] Falling back to alternative method (navigate_saved_searches2)")
                try:
                    if driver is not None:
                        navigate_saved_searches2()
                    else:
                        print(f"[SAVED SEARCHES] Cannot use fallback - driver is None")
                except Exception as fallback_error:
                    print(f'[SAVED SEARCHES] ERROR in fallback navigation: {fallback_error}')
                    print(f'[SAVED SEARCHES] Driver remains open, continuing...')
                searches = dict()
                netnew = dict()
                titles = ['Net New', 'Saved']
                print(f"[SAVED SEARCHES] Using fallback titles: {titles}")

                try:
                    if driver is None or wait is None:
                        raise Exception("Driver or wait is None")
                    view_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@data-name='views']")))
                    view_button.click()
                    time.sleep(1)

                    your_views_tab = wait.until(EC.element_to_be_clickable((By.ID, "private")))
                    your_views_tab.click()
                    time.sleep(1)

                    view_options = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//div[@role='option']")))
                    time.sleep(1)
                    view_options[0].click()
                    time.sleep(2)
                except Exception as view_error:
                    print(f'[SAVED SEARCHES] ERROR in fallback view selection: {view_error}')
                    print(f'[SAVED SEARCHES] Driver remains open, skipping view processing...')
                    view_options = []

                print(f'[SAVED SEARCHES] Starting to process {len(view_options)} view options')
                for i in range(len(view_options)):
                    print(f'[SAVED SEARCHES] Processing view option {i+1}/{len(view_options)}')
                    try:
                        if driver is None or wait is None:
                            raise Exception("Driver or wait is None")
                        
                        print(f'[SAVED SEARCHES] Opening views dropdown...')
                        view_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@data-name='views']")))
                        view_button.click()
                        time.sleep(1)

                        print(f'[SAVED SEARCHES] Clicking private tab...')
                        your_views_tab = wait.until(EC.element_to_be_clickable((By.ID, "private")))
                        your_views_tab.click()
                        time.sleep(1)

                        print(f'[SAVED SEARCHES] Getting view options...')
                        view_options = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//div[@role='option']")))
                        view_option_text = view_options[i].text
                        print(f'[SAVED SEARCHES] Selected view option {i+1}: "{view_option_text}"')

                        # Skip empty/placeholder option rows (e.g. a trailing blank "create view" row)
                        if not view_option_text.strip():
                            print(f'[SAVED SEARCHES] Skipping empty view option {i+1}')
                            continue

                        print(f'[SAVED SEARCHES] Clicking on view option...')
                        view_options[i].click()
                        print(f'[SAVED SEARCHES] Waiting 6 seconds for page to load...')
                        time.sleep(6)

                        # Extract data for each title after clicking the view
                        print(f'[SAVED SEARCHES] Starting data extraction for view "{view_option_text}"')
                        for title in titles:
                            print(f"[SAVED SEARCHES] ##### Extracting for '{title}' in view '{view_option_text}' #####")
                            try:
                                if driver is None or wait is None:
                                    raise Exception("Driver or wait is None")
                                
                                # The view's count widgets look like:
                                #   <div class="zp_PfDqP">Net New<div><span data-count-size="small">8.5K</span></div></div>
                                xpath_expression = f"//div[normalize-space(text())='{title}']//span[@data-count-size]"
                                print(f"[SAVED SEARCHES] Waiting for element with XPath: {xpath_expression}")
                                count_element = wait.until(EC.presence_of_element_located((By.XPATH, xpath_expression)))

                                count_value = count_element.text.strip()
                                print(f"[SAVED SEARCHES] Extracted raw count for '{title}': '{count_value}'")

                                # Convert count value
                                if count_value and len(count_value) > 0:
                                    if count_value[-1].lower() == 'k':
                                        count_value = float(count_value[:-1]) * 1000
                                    elif count_value[-1].lower() == 'm':
                                        count_value = float(count_value[:-1]) * 1000000
                                    else:
                                        count_value = float(count_value)
                                    
                                    if title == "Net New":
                                        netnew[view_option_text] = count_value
                                        print(f"[SAVED SEARCHES] ✅ Stored Net New for '{view_option_text}': {count_value:,}")
                                    else:
                                        searches[view_option_text] = count_value
                                        print(f"[SAVED SEARCHES] ✅ Stored Saved for '{view_option_text}': {count_value:,}")
                                else:
                                    print(f"[SAVED SEARCHES] ⚠️  Empty count value for '{title}'")

                                time.sleep(2)

                            except Exception as extract_error:
                                print(f"[SAVED SEARCHES] ❌ ERROR extracting data for title '{title}' in view '{view_option_text}': {extract_error}")
                                import traceback
                                print(f"[SAVED SEARCHES] Traceback: {traceback.format_exc()}")

                    except Exception as view_loop_error:
                        print(f'[SAVED SEARCHES] ❌ ERROR in view loop iteration {i+1}: {view_loop_error}')
                        print(f'[SAVED SEARCHES] Driver remains open, continuing to next iteration...')
                        import traceback
                        print(f'[SAVED SEARCHES] Traceback: {traceback.format_exc()}')
                        continue
                
                print(f'[SAVED SEARCHES] Finished processing all view options')
                print(f'[SAVED SEARCHES] Final searches dict: {searches}')
                print(f'[SAVED SEARCHES] Final netnew dict: {netnew}')

        
            print('\n[SAVED SEARCHES] ========== COMPLETED PROCESSING ==========')
            print(f'[SAVED SEARCHES] Searches dict: {searches}')
            print(f'[SAVED SEARCHES] NetNew dict: {netnew}')
            print('[SAVED SEARCHES] Reached here - preparing to save data\n')
            apollo_search_field['status'] = 'completed'
            apollo_search_field['last_execution'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            apollo_search_field['used_credits'] = used_credits
            apollo_search_field['total_credits'] = total_credits
            apollo_search_field['renews_on'] = renewal_date.strftime('%Y-%m-%d %H:%M:%S') if renewal_date else None
            apollo_search_field['saved_titles'] = "\n".join(list(searches.keys())) if searches else ""
            apollo_search_field['saved_counts'] = "\n".join([str(int(i)) for i in list(searches.values())]) if searches else ""
            apollo_search_field['total_saved'] = sum(list(searches.values())) if searches else 0
            apollo_search_field['netnew_counts'] = "\n".join([str(int(i)) for i in list(netnew.values())]) if netnew else ""
            apollo_search_field['total_netnew'] = sum(list(netnew.values())) if netnew else 0
            
            print(f'[SAVED SEARCHES] Data being saved:')
            print(f'[SAVED SEARCHES]   saved_titles: "{apollo_search_field["saved_titles"]}"')
            print(f'[SAVED SEARCHES]   saved_counts: "{apollo_search_field["saved_counts"]}"')
            print(f'[SAVED SEARCHES]   total_saved: {apollo_search_field["total_saved"]}')
            print(f'[SAVED SEARCHES]   netnew_counts: "{apollo_search_field["netnew_counts"]}"')
            print(f'[SAVED SEARCHES]   total_netnew: {apollo_search_field["total_netnew"]}')
            # driver.quit()
            time.sleep(2)

        except Exception as e:
            print(f'[SEARCH DATA] ========== TOP LEVEL EXCEPTION ==========')
            print(f'[SEARCH DATA] Error: {e}')
            print(f'[SEARCH DATA] Exception type: {type(e).__name__}')
            import traceback
            print(f'[SEARCH DATA] Full traceback:\n{traceback.format_exc()}')
            print(f'[SEARCH DATA] Driver will remain open - error handled gracefully')
            apollo_search_field['status'] = 'failed'
            apollo_search_field['failed_reason'] = str(e)
        # data_field['failed_reason'] = str(e)
        csv_path = APOLLO_SEARCH_DATA_CSV
        new_entry = pd.DataFrame([apollo_search_field])  # `data_field` is a dict with the new row

        # Step 1: Load existing CSV (if it exists)
        if os.path.exists(csv_path):
            try:
                df = pd.read_csv(csv_path)
                df = df[df['email'] != apollo_search_field['email']]
            except:
                df = pd.DataFrame()

            # Step 2: Remove rows with same email as new entry
            

            # Step 3: Append new entry
            df = pd.concat([new_entry, df], ignore_index=True)
        else:
            # First time creating the file
            df = new_entry
        safe_save_csv(df, csv_path)

    email_credits = []
    provided_monthly_credits = []
    if not condition2:
        print(f'[CREDITS DATA] Starting credits data extraction for {email}')
        print(f'[CREDITS DATA] Driver status: {"Valid" if driver else "None/Invalid"}')
        
        try:
            # Wrap entire credits section in try-catch to prevent driver from closing
            try:
                # soup = BeautifulSoup(driver.page_source, "html.parser")
                time.sleep(20)
                print('[CREDITS DATA] going to credits\n\n')
                if driver is None:
                    raise Exception("Driver is None - cannot proceed with credits extraction")
                driver.get("https://app.apollo.io/#/settings/credits/current")
                time.sleep(7 + random.uniform(-1, 2))  # wait for page load

                # Drop any Cloudflare challenge BEFORE reading the page: the overlay
                # leaves the text behind it readable, so without this the renewal/credits
                # parse can appear to work while the chart never renders.
                clear_cloudflare_challenge(driver)

                page_text_temp = driver.find_element(By.TAG_NAME, 'body').text
            except Exception as credits_page_error:
                print(f'[CREDITS DATA] ERROR loading credits page: {credits_page_error}')
                print(f'[CREDITS DATA] Driver will remain open, continuing...')
                raise  # Re-raise to be caught by outer try-catch
            # Works across all known layouts (credits/mo, emails/mo, new donut UI).
            used_credits, total_credits_provided = extract_credit_usage(page_text_temp)

            # Parse the page source
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, "html.parser")
            page_text = soup.get_text()
            time.sleep(1 + random.uniform(-1, 2))

            renewal_date = extract_renewal_date(
                body_text=page_text_temp,
                soup_text=page_text,
                current_url=driver.current_url,
            )

            if not renewal_date:
                # Genuinely unreadable: an unchallenged page whose renewal text is
                # missing in every known form AND whose URL carries no minDate.
                # Raise rather than `continue` - a bare continue skipped both the CSV
                # save below (losing the 'failed' status) and safe_quit(driver) at the
                # end of the loop, which leaked Chrome and locked the next profile.
                print('[CREDITS DATA] Renewal date not found in any known layout')
                logging.info(f'{email}: renewal date not found in any known layout')
                raise Exception('renewal date not found (unrecognised credits layout)')

            dates = get_past_renewal_credit_periods(renewal_date)
            days_to_renew = (renewal_date - datetime.now()) <= timedelta(days=7)  # 5 days = 120hrs
            # print(dates)
            #    
            for min_date, max_date in dates:
                min_date_str = min_date.strftime("%Y-%m-%d")
                max_date_str = max_date.strftime("%Y-%m-%d")
                # Apollo's credit page is a hash-router SPA: calling driver.get() on a
                # history URL that differs only AFTER the '#' does NOT refetch — the date
                # filter stays stale and every month reports the same number. Force a full
                # reload via about:blank so the page re-reads minDate/maxDate from the URL.
                driver.get("about:blank")
                time.sleep(1)
                driver.get(f"https://app.apollo.io/#/settings/credits/history?minDate={min_date_str}&maxDate={max_date_str}")
                time.sleep(3)

                # A challenge here stops the usage chart from rendering, so the widget
                # wait below times out and the month is recorded as None.
                clear_cloudflare_challenge(driver)

                if detect_force_logout(driver):
                    if driver:
                        driver.quit()
                    # raise Exception("Apollo forced logout detected while fetching history")

                # The "N credits used" total lives in a stable element:
                #   <div data-testid="credit-usage-history-chart-credits-used"
                #        aria-label="3,848 credits used">
                credits_used = None
                credits_used_re = r'([\d,]+)\s+credits?\s+used'
                try:
                    el = WebDriverWait(driver, 25).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, '[data-testid="credit-usage-history-chart-credits-used"]')
                        )
                    )
                    time.sleep(2 + random.uniform(0, 1))  # let the value settle after the filter applies
                    label = el.get_attribute("aria-label") or el.text or ""
                    m = re.search(credits_used_re, label, re.IGNORECASE)
                    if m:
                        credits_used = int(m.group(1).replace(',', ''))
                except Exception as hist_err:
                    print(f"[CREDITS HISTORY] widget not found for {min_date_str}..{max_date_str}: {hist_err}")

                # Fallback: scan the whole page text for the same "N credits used" phrase.
                if credits_used is None:
                    try:
                        body_text = driver.find_element(By.TAG_NAME, "body").text
                        m = re.search(credits_used_re, body_text, re.IGNORECASE)
                        if m:
                            credits_used = int(m.group(1).replace(',', ''))
                    except Exception:
                        pass

                if credits_used is not None:
                    print(f"[CREDITS HISTORY] {min_date_str}..{max_date_str} -> {credits_used} credits used")
                    email_credits.append(credits_used)
                    provided_monthly_credits.append(total_credits_provided if total_credits_provided else 10000)
                    if total_credits_provided == 0:
                        total_credits_provided = 10000
                else:
                    print(f"[CREDITS HISTORY] No 'credits used' value found for {min_date_str}..{max_date_str}")
                    email_credits.append(None)
                    provided_monthly_credits.append(None)
                time.sleep(2)

            # Did ANY month actually yield a number? Checked before padding, since
            # padding masks the difference between "no value" and "-1".
            got_any_month = any(c is not None for c in email_credits)

            while len(email_credits) < 6:
                email_credits.append(-1)
            email_credits = email_credits[::-1]
            while len(provided_monthly_credits) < 6:
                provided_monthly_credits.append(-1)
            provided_monthly_credits = provided_monthly_credits[::-1]
            if total_credits_provided == 0:
                total_credits_provided = provided_monthly_credits[0]
            apollo_credits_field['first_month_credits'] = email_credits[0]
            apollo_credits_field['second_month_credits'] = email_credits[1]
            apollo_credits_field['third_month_credits'] = email_credits[2]
            apollo_credits_field['fourth_month_credits'] = email_credits[3]
            apollo_credits_field['fifth_month_credits'] = email_credits[4]
            apollo_credits_field['sixth_month_credits'] = email_credits[5]
            apollo_credits_field['first_month_provided'] = total_credits_provided
            apollo_credits_field['second_month_provided'] = provided_monthly_credits[1]
            apollo_credits_field['third_month_provided'] = provided_monthly_credits[2]
            apollo_credits_field['fourth_month_provided'] = provided_monthly_credits[3]
            apollo_credits_field['fifth_month_provided'] = provided_monthly_credits[4]
            apollo_credits_field['sixth_month_provided'] = provided_monthly_credits[5]
            formatted_date = renewal_date.strftime('%d %B %Y, %H:%M:%S')
            apollo_credits_field['renewal_date'] = renewal_date.strftime('%Y-%m-%d %H:%M:%S')
            apollo_credits_field['last_execution'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Every month came back empty => the chart never rendered (Cloudflare, a
            # layout we don't handle yet, or a slow load). Record that as 'failed' so
            # the next run retries. Marking it 'completed' wrote an empty row that the
            # skip check then treated as good data, freezing it in place.
            if not got_any_month:
                apollo_credits_field['status'] = 'failed'
                print(f'[CREDITS DATA] No month values extracted for {email} - marking failed')
                logging.info(f'{email}: credits marked failed - no month values extracted')
            else:
                apollo_credits_field['status'] = 'completed'
        except Exception as e:
            apollo_credits_field['status'] = 'failed'
            print(f"Error processing {email}: {e}")
            logging.info(f'{email}: credits extraction failed - {e}')
        csv_path_credits = APOLLO_CREDITS_DATA_CSV
        new_entry_credits = pd.DataFrame([apollo_credits_field])  # `data_field` is a dict with the new row

        # Step 1: Load existing CSV (if it exists)
        if os.path.exists(csv_path_credits):
            try:
                df_credits = pd.read_csv(csv_path_credits)
                df_credits = df_credits[df_credits['email'] != apollo_credits_field['email']]
            except:
                df_credits = pd.DataFrame()
            # df_credits = pd.read_csv(csv_path_credits, names=columns_apollo_credits, header=None)

            # Step 2: Remove rows with same email as new entry
            # df_credits = df_credits[df_credits['email'] != apollo_credits_field['email']]

            # Step 3: Append new entry
            df_credits = pd.concat([new_entry_credits, df_credits], ignore_index=True)
        else:
            # First time creating the file
            df_credits = new_entry_credits
        safe_save_csv(df_credits, csv_path_credits)
        time.sleep(random.uniform(20, 30))
        
    if not condition3:
        # ========== UPLOAD DATA EXTRACTION ==========
        print(f"\n[UPLOAD DATA] Starting upload data extraction for {email}")
        print(f'[UPLOAD DATA] Driver status: {"Valid" if driver else "None/Invalid"}')
        try:
            # Wrap entire upload section in try-catch to prevent driver from closing
            try:
                link = 'https://app.apollo.io/#/lists?groupBy[]=labelModality&perPage=25&sortByField=updated_at&sortAscending=false'
                print(f"[UPLOAD DATA] Navigating to lists page: {link}")
                if driver is None:
                    raise Exception("Driver is None - cannot proceed with upload extraction")
                driver.get(link)
                time.sleep(7)
            except Exception as upload_page_error:
                print(f'[UPLOAD DATA] ERROR loading upload page: {upload_page_error}')
                print(f'[UPLOAD DATA] Driver will remain open, continuing...')
                raise  # Re-raise to be caught by outer try-catch
            

            # The lists page is grouped by modality: a header row ("List name" / no
            # aria-rowindex), then data rows. Columns: col1=name, col2=count,
            # col3=type (People/Companies), col5=Last Modified ("N days ago").
            # We work directly with the Selenium row elements (no soup + magic offset)
            # so each row's own col5 tooltip can be hovered for the precise date.
            print(f"[UPLOAD DATA] Waiting for rows to render...")
            time.sleep(5)
            row_elements = driver.find_elements(By.CSS_SELECTOR, "div[role='row']")
            print(f"[UPLOAD DATA] Found {len(row_elements)} row elements")

            data = []
            MAX_PEOPLE_ROWS = 15  # take the first 15 People entries

            def _cell_text(row_el, colindex):
                try:
                    return row_el.find_element(
                        By.CSS_SELECTOR, f"[aria-colindex='{colindex}']").text.strip()
                except Exception:
                    return ""

            for row_el in row_elements:
                if len(data) >= MAX_PEOPLE_ROWS:
                    break
                try:
                    # Header rows have no data aria-rowindex; skip them.
                    if row_el.get_attribute("aria-rowindex") is None:
                        continue

                    name = _cell_text(row_el, 1)
                    count = _cell_text(row_el, 2)
                    row_type = _cell_text(row_el, 3)

                    # Skip headers / empty rows; only keep People-type lists.
                    if not name or name.lower().strip() == 'list name':
                        continue
                    if row_type.lower().strip() != 'people':
                        continue

                    visible_date = _cell_text(row_el, 5)

                    # Precise date via tooltip hover on THIS row's col5 trigger.
                    full_date = ""
                    try:
                        trigger = row_el.find_element(
                            By.CSS_SELECTOR, "[aria-colindex='5'] span[data-has-tooltip='true']")
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", trigger)
                        time.sleep(0.3)
                        ActionChains(driver).move_to_element(trigger).pause(0.3).perform()
                        tooltip = WebDriverWait(driver, 6).until(
                            EC.visibility_of_element_located((By.CSS_SELECTOR, '[role="tooltip"]')))
                        full_date = tooltip.text.strip()
                    except Exception as tip_err:
                        print(f"[UPLOAD DATA] '{name}' - tooltip date failed, using visible date: {tip_err}")

                    temp_filed = {
                        "name": name,
                        "count": count,
                        "date_visible": visible_date,
                        "date_full": full_date,
                    }
                    data.append(temp_filed)
                    print(f"[UPLOAD DATA] +{len(data)}/{MAX_PEOPLE_ROWS}: {temp_filed}")
                    time.sleep(random.uniform(0.5, 1.0))

                except Exception as e:
                    print(f"[UPLOAD DATA] Row parse error: {e}")

            print(f"[UPLOAD DATA] Total data extracted: {len(data)} items")
            apollo_upload_filed["data"] = data
            apollo_upload_filed['last_execution'] = datetime.now()
            
            if len(data) > 0:
                # Check how many have full dates
                full_dates_count = sum(1 for d in data if d.get('date_full', '').strip())
                visible_dates_count = sum(1 for d in data if d.get('date_visible', '').strip())
                
                if full_dates_count == len(data):
                    apollo_upload_filed["status"] = 'completed'
                    print(f"[UPLOAD DATA] Status: SUCCESS - All {len(data)} items have full dates")
                elif full_dates_count > 0 or visible_dates_count > 0:
                    apollo_upload_filed["status"] = 'partial'
                    print(f"[UPLOAD DATA] Status: PARTIAL - {len(data)} items, {full_dates_count} full dates, {visible_dates_count} visible dates")
                else:
                    apollo_upload_filed["status"] = 'partial'
                    print(f"[UPLOAD DATA] Status: PARTIAL - {len(data)} items but no dates available")
            else:
                apollo_upload_filed["status"] = 'failed'
                print(f"[UPLOAD DATA] Status: FAILED - No data extracted")
                        
        except Exception as e:
            print(f'[UPLOAD DATA] ========== UPLOAD EXTRACTION EXCEPTION ==========')
            print(f"[UPLOAD DATA] Error processing {email}: {e}")
            print(f'[UPLOAD DATA] Exception type: {type(e).__name__}')
            import traceback
            print(f'[UPLOAD DATA] Full traceback:\n{traceback.format_exc()}')
            print(f'[UPLOAD DATA] Driver will remain open - error handled gracefully')
            apollo_upload_filed["data"] = data if 'data' in locals() else []
            apollo_upload_filed['last_execution'] = datetime.now()
            apollo_upload_filed["status"] = 'failed'
        
        # ========== DATA PROCESSING ==========
        print(f"\n[DATA PROCESSING] Starting data processing for {email}")
        if len(apollo_upload_filed['data']) > 0 and apollo_upload_filed['status'] in ['completed', 'partial']:
            print(f"[DATA PROCESSING] Processing {len(apollo_upload_filed['data'])} records")
            records = apollo_upload_filed['data'].copy()
            today = datetime.now()
            
            # Include ALL data now (including monthly and email data)
            # Use full_date if available, otherwise fall back to visible_date
            processed_records = []
            for r in records:
                try:
                    # Skip invalid records
                    # Only check for actual header values, not "People" which is valid data
                    if (r.get('name', '') in ["List name", "# of Records", "Type"] or 
                        r.get('count', '') in ["# of Records", "Type"] or
                        r.get('date_visible', '') in ["Type"]):
                        print(f"[DATA PROCESSING] Skipping invalid record: {r.get('name', 'Unknown')}")
                        continue
                    
                    if r.get('date_full') and r['date_full'].strip():
                        date_to_use = convert_date(r['date_full'])
                    elif r.get('date_visible') and r['date_visible'].strip():
                        # Try to parse visible date as fallback
                        try:
                            # For visible dates like "7 days ago", "1 month ago", etc.
                            # We need to calculate the actual date
                            visible_date = r['date_visible'].strip()
                            if 'days ago' in visible_date:
                                days = int(visible_date.split()[0])
                                date_to_use = datetime.now() - timedelta(days=days)
                            elif 'months ago' in visible_date:
                                months = int(visible_date.split()[0])
                                date_to_use = datetime.now() - timedelta(days=months*30)  # Approximate
                            elif 'month ago' in visible_date:
                                date_to_use = datetime.now() - timedelta(days=30)  # Approximate
                            else:
                                # Try to parse as regular date
                                date_to_use = convert_date(visible_date)
                        except:
                            # If visible date parsing fails, use current date
                            date_to_use = datetime.now()
                            print(f"[DATA PROCESSING] Using current date for {r.get('name', 'Unknown')} (date parsing failed)")
                    else:
                        date_to_use = datetime.now()
                        print(f"[DATA PROCESSING] Using current date for {r.get('name', 'Unknown')} (no date available)")
                    
                    processed_records.append({
                        'name': r.get('name', f'Unknown_{len(processed_records)}'),
                        'count': convert_count(r.get('count', '0')),
                        'date': date_to_use
                    })
                except Exception as e:
                    print(f"[DATA PROCESSING] Error processing record {r.get('name', 'Unknown')}: {e}")
                    # Still add the record with current date
                    processed_records.append({
                        'name': r.get('name', f'Unknown_{len(processed_records)}'),
                        'count': convert_count(r.get('count', '0')),
                        'date': datetime.now()
                    })
            
            filtered_records = []
            for record in processed_records:
                if 'monthly' in record['name'].lower():
                    print('This is not includable')
                else:
                    filtered_records.append(record)

            upload_df = pd.DataFrame(filtered_records)
            print(f"[DATA PROCESSING] Created DataFrame with {len(upload_df)} rows")
            upload_df = upload_df.sort_values(by='date', ascending=False).reset_index(drop=True)
            
            # Group by month instead of by date proximity
            upload_df['year_month'] = upload_df['date'].dt.to_period('M')
            print(f"[DATA PROCESSING] Added year_month column")
            
            # Get the last N months (current + previous months)
            current_month = pd.Timestamp(today).to_period('M')
            target_months = [current_month - i for i in range(MONTHS_TO_INCLUDE)]
            print(f"[DATA PROCESSING] Target months: {target_months}")
            
            # Filter data for last N months only
            recent_data = upload_df[upload_df['year_month'].isin(target_months)]
            print(f"[DATA PROCESSING] Recent data (last {MONTHS_TO_INCLUDE} months): {len(recent_data)} rows")
            
            # Get current month data only for data_count
            current_month_data = upload_df[upload_df['year_month'] == current_month]
            current_month_count = current_month_data['count'].sum() if len(current_month_data) > 0 else 0
            print(f"[DATA PROCESSING] Current month ({current_month}) count: {current_month_count:,}")
            
            # Group by month and process individual records (keep all files separately)
            def process_month_group(group):
                """Process a month's records: sort by date ascending, number them, and build flat structure"""
                # Sort by date ascending (oldest first)
                sorted_group = group.sort_values(by='date', ascending=True).reset_index(drop=True)
                
                # Build result dictionary
                result = {}
                total_count = 0
                latest_date = None
                
                # Number each record sequentially (1 = oldest, 2, 3, etc. = newer)
                for idx, row in sorted_group.iterrows():
                    file_num = idx + 1  # Start numbering from 1
                    result[f'count_{file_num}'] = int(row['count'])
                    result[f'date_{file_num}'] = row['date'].strftime('%Y-%m-%d %H:%M:%S')
                    total_count += int(row['count'])
                    # Track latest date (last one in sorted ascending order is the newest)
                    latest_date = row['date'].strftime('%Y-%m-%d %H:%M:%S')
                
                result['total_count'] = total_count
                result['latest_date'] = latest_date if latest_date else None
                
                return result
            
            # Process each month group
            monthly_data_dict = {}
            for month_period, group in recent_data.groupby('year_month'):
                monthly_data_dict[month_period] = process_month_group(group)
            
            # Ensure all target months are included, even with 0 counts
            monthly_breakdown = []
            for month_period in target_months:
                # Check if this month has data
                month_data = monthly_data_dict.get(month_period)
                
                month_str = month_period.strftime('%Y-%m')  # e.g., '2025-10'
                month_name = month_period.strftime('%b %Y')  # e.g., 'Oct 2025'
                
                if month_data:
                    # Month has data - include all individual file data
                    month_entry = {
                        'year_month': month_str,
                        'month_name': month_name,
                        'total_count': month_data['total_count'],
                        'latest_date': month_data['latest_date']
                    }
                    # Add all individual count and date fields
                    for key, value in month_data.items():
                        if key not in ['total_count', 'latest_date']:
                            month_entry[key] = value
                    monthly_breakdown.append(month_entry)
                else:
                    # Month has no data - set to 0
                    monthly_breakdown.append({
                        'year_month': month_str,
                        'month_name': month_name,
                        'total_count': 0,
                        'latest_date': None
                    })
            
            print(f"[DATA PROCESSING] Monthly breakdown (all {MONTHS_TO_INCLUDE} months): {monthly_breakdown}")
            
            # ========== LAST UPLOADED DATA COUNT CALCULATION ==========
            # Apply the same logic as sk_test.py to get recent uploaded data count
            print(f"[DATA PROCESSING] Calculating last_uploaded_data count using grouping logic...")
            
            # Filter out monthly and email data for last_uploaded_data calculation
            
            if filtered_records:
                filtered_df = pd.DataFrame(filtered_records)
                filtered_df = filtered_df.sort_values(by='date', ascending=False).reset_index(drop=True)
                print(f"[DATA PROCESSING] Filtered records for last_uploaded_data: {len(filtered_df)} rows")
                
                # Apply grouping logic from sk_test.py
                groups = []
                current_group = []
                
                for i, row in filtered_df.iterrows():
                    if row['count'] < 1000:
                        continue
                    
                    if not current_group:
                        current_group.append(row)
                    else:
                        last_date = current_group[-1]['date']
                        if abs((row['date'] - last_date).days) <= 1:
                            current_group.append(row)
                        else:
                            groups.append(current_group)
                            current_group = [row]
                
                if current_group:
                    groups.append(current_group)
                
                # Apply second rule: look for solo uploads with ≥10K
                for i, row in filtered_df.iterrows():
                    is_already_grouped = any(row['name'] in [r['name'] for r in g] for g in groups)
                    if not is_already_grouped and row['count'] >= 3000:
                        groups.append([row])
                
                # Calculate total count from the first group (most recent uploads)
                if groups:
                    usable_data_list = groups[0]
                    last_uploaded_data_count = 0
                    date_list = []
                    for usable_data in usable_data_list:
                        last_uploaded_data_count += usable_data['count']
                        date_list.append(usable_data['date'])
                    
                    if date_list:
                        last_uploaded_date = max(date_list)
                    else:
                        last_uploaded_date = apollo_upload_filed['last_execution']
                    
                    print(f"[DATA PROCESSING] Last uploaded data count: {last_uploaded_data_count:,}")
                else:
                    last_uploaded_data_count = 0
                    last_uploaded_date = apollo_upload_filed['last_execution']
                    print(f"[DATA PROCESSING] No groups found, last_uploaded_data_count: 0")
            else:
                last_uploaded_data_count = 0
                last_uploaded_date = apollo_upload_filed['last_execution']
                print(f"[DATA PROCESSING] No filtered records, last_uploaded_data_count: 0")
            
            # Calculate totals
            if len(recent_data) > 0:
                if 'last_uploaded_date' not in locals():
                    last_uploaded_date = recent_data['date'].max()
            else:
                if 'last_uploaded_date' not in locals():
                    last_uploaded_date = apollo_upload_filed['last_execution']
            print(f"[DATA PROCESSING] Current month count: {current_month_count:,}, Last uploaded: {last_uploaded_date}, Last uploaded data count: {last_uploaded_data_count:,}")
        else:
            print(f"[DATA PROCESSING] Skipping processing - status: {apollo_upload_filed['status']}, data length: {len(apollo_upload_filed.get('data', []))}")
            current_month_count = 0
            last_uploaded_data_count = 0
            last_uploaded_date = apollo_upload_filed['last_execution']
            monthly_breakdown = []
        
        # ========== SAVE TO CSV ==========
        print(f"\n[CSV SAVE] Preparing to save data for {email}")
        # Convert monthly_breakdown to string for CSV compatibility
        monthly_breakdown_str = str(monthly_breakdown) if monthly_breakdown else ""
        
        final_filed = {
            'email': apollo_upload_filed['email'],
            'data_count': last_uploaded_data_count,
            'last_uploaded': last_uploaded_date,
            'status': apollo_upload_filed['status'],
            'last_execution': apollo_upload_filed['last_execution'],
            'monthly_breakdown': monthly_breakdown_str
        }
        print(f"[CSV SAVE] Final data: {final_filed}")
        
        temp_upload_df = pd.DataFrame([final_filed])
        csv_path = APOLLO_UPLOAD_DATA_CSV
        
        if os.path.exists(csv_path):
            try:
                temp_upload_df1 = pd.read_csv(csv_path)
                temp_upload_df1 = temp_upload_df1[temp_upload_df1['email'] != final_filed['email']]
                temp_upload_df = pd.concat([temp_upload_df, temp_upload_df1], ignore_index=True)
                print(f"[CSV SAVE] Updated existing CSV file")
            except Exception as e:
                print(f"[CSV SAVE] Error reading existing CSV: {e}")
                temp_upload_df1 = pd.DataFrame()
                temp_upload_df = pd.concat([temp_upload_df, temp_upload_df1], ignore_index=True)
        else:
            print(f"[CSV SAVE] Creating new CSV file")
            
        safe_save_csv(temp_upload_df, csv_path)
        print(f"[CSV SAVE] Successfully saved to {csv_path}")
        time.sleep(random.uniform(20, 30))

    print(f'[LOOP END] Finished processing email: {email}')
    
    # Check if all sections were skipped
    if condition1 and condition2 and condition3:
        print(f'[LOOP END] All sections were skipped - closing driver (nothing to process)')
        print(f'[LOOP END] Email was processed recently, so no data extraction was needed')
    else:
        print(f'[LOOP END] Processing completed - closing driver')
    
    print(f'[LOOP END] Closing driver and taking break...')
    safe_quit(driver)
    print(f'Taking break for {SLEEP_BETWEEN_ACCOUNTS} seconds.')
    time.sleep(SLEEP_BETWEEN_ACCOUNTS)

# Functions moved to top of file

def apollo_upload_data_insertion(all_data):
# Parse and filter
    final_data_list = []
    for data in all_data:
        if len(data['data']) > 0 and data['status'] == 'success' and all(d['date_full'] != '' for d in data['data']):
            records = data['data'].copy()
            today = datetime.now()
            
            # Include ALL data now (including monthly and email data)
            upload_df = pd.DataFrame([
                {
                    'name': r['name'],
                    'count': convert_count(r['count']),
                    'date': convert_date(r['date_full'])
                }
                for r in records
            ])
            upload_df = upload_df.sort_values(by='date', ascending=False).reset_index(drop=True)
            
            # Group by month instead of by date proximity
            upload_df['year_month'] = upload_df['date'].dt.to_period('M')
            
            # Get the last N months (current + previous months)
            current_month = pd.Timestamp(today).to_period('M')
            target_months = [current_month - i for i in range(MONTHS_TO_INCLUDE)]
            
            # Filter data for last 3 months only
            recent_data = upload_df[upload_df['year_month'].isin(target_months)]
            
            # Group by month and sum counts
            monthly_data = recent_data.groupby('year_month').agg({
                'count': 'sum',
                'date': 'max'  # Get the latest date in each month
            }).reset_index()
            
            # Calculate totals
            total_count = recent_data['count'].sum()
            if len(recent_data) > 0:
                last_uploaded_date = recent_data['date'].max()
            else:
                last_uploaded_date = data['last_execution']
                
            # Store monthly breakdown for detailed analysis
            monthly_breakdown = monthly_data.to_dict('records')
        else:
            total_count = 0
            last_uploaded_date = data['last_execution']
            monthly_breakdown = []
            
        final_filed = {
            'email' : data['email'],
            'data_count' : total_count,
            'last_uploaded' : last_uploaded_date,
            'status' : data['status'],
            'last_execution' : data['last_execution'],
            'monthly_breakdown' : monthly_breakdown
        }
        final_data_list.append(final_filed)

    data_to_insert = pd.DataFrame(final_data_list).sort_values(by='last_uploaded',ascending=False).reset_index(drop=True)
    return data_to_insert
# data_to_insert = apollo_upload_data_insertion(apollo_upload_details)
# data_to_insert.to_csv(r'C:\Users\Test\Desktop\apollo_scraper\apollo_upload_data.csv', index=False)

def UploadToAWS(local_file, bucket_name, s3_file):
    s3 = boto3.client(
        's3',
        aws_access_key_id = access_key,
        aws_secret_access_key = secret_key,
        region_name = "ap-south-1"
    )
    try:
        s3.upload_file(local_file, bucket_name, s3_file)
        print("Upload To AWS Successful")
        return True
    except FileNotFoundError:
        print("The file was not found")
        return False
timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

# AWS Upload (if enabled)
if ENABLE_AWS_UPLOAD:
    print("Uploading data to AWS S3...")
    UploadToAWS(APOLLO_SEARCH_DATA_CSV, 'apollo-tables', f'apollo_searches_{timestamp}.csv')
    UploadToAWS(APOLLO_CREDITS_DATA_CSV, 'apollo-tables', f'apollo_credits_{timestamp}.csv')
    UploadToAWS(APOLLO_UPLOAD_DATA_CSV, 'apollo-tables', f'apollo_upload_data_{timestamp}.csv')
    print("✅ Uploaded All Apollo Account Data to AWS")
else:
    print("ℹ️  AWS upload disabled. Data saved locally only.")

print("✅ Extracted All Apollo Account Data. Please Close This Window")