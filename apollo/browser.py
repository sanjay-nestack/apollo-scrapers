"""Chrome process + driver lifecycle and page-state probes. All functions take a
driver explicitly — no module globals."""
import os
import time
import random
import logging
import subprocess
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


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


def safe_quit(drv):
    """Attempt to quit the webdriver; ignore any errors."""
    try:
        if drv:
            drv.quit()
    except Exception:
        pass


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
