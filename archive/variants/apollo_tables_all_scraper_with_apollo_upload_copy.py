import os
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
for h in logging.root.handlers[:]:
    logging.root.removeHandler(h)

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
    BASE_FOLDER_PATH = r'C:\Users\Test\Desktop\apollo_scraper'
    MAX_ROWS_TO_PROCESS = 15
    SLEEP_BETWEEN_ACCOUNTS = 900
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
    try:
        return datetime.strptime(dstr, "%b %d, %Y %I:%M %p")
    except:
        try:
            # Try alternative format
            return datetime.strptime(dstr, "%Y-%m-%d %H:%M:%S")
        except:
            return datetime.now()

def navigate_saved_searches():
    time.sleep(5)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
    driver.get("https://app.apollo.io/#/people")
    time.sleep(5)

    wait.until(EC.visibility_of_element_located((By.LINK_TEXT, "Saved searches"))).click()
    time.sleep(5)
    wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Private')]"))).click()
    time.sleep(5)

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

# https://docs.google.com/spreadsheets/d/1kKqEfKLSW9cUtcjmNlinxeYXt-EtcXm5B5c4m7_CnbI/edit?pli=1&gid=0#gid=0
sheet_url = "https://docs.google.com/spreadsheets/d/1kKqEfKLSW9cUtcjmNlinxeYXt-EtcXm5B5c4m7_CnbI/export?format=csv&gid=0"
df = pd.read_csv(sheet_url)
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
    'total_netnew'
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
    'sixth_month_credits'
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

email_number = 1
for index, row in final_df_sorted.iterrows():
    email = row["Email"]
    logging.info(f'Index: {email_number} - Running for {email}')
    email_number += 1

    if TARGET_EMAIL and (email.lower().strip() not in TARGET_EMAIL):
        print(f"Skipping {email} as it is not {TARGET_EMAIL}")
        continue
    # if (row['renewal_date'] is not None) and (row['renewal_date'] > (datetime.now() + timedelta(days=10))):
    #     print(f"{email} - Renewal date is more than 10 days from now. Skipping.")
    #     continue

    # If apollo_search_data is not empty and email exists
    hours_to_check = 20
    condition1 = False
    if not apollo_search_data.empty and email in apollo_search_data['email'].values:
        existing_row = apollo_search_data[apollo_search_data['email'] == email].iloc[0]

        if (existing_row['status'] == 'completed') and (pd.to_datetime(existing_row['last_execution']) > (datetime.now() - timedelta(hours=hours_to_check))):
            logging.info(f'Last execution was on {existing_row['last_execution']} for email {email} and current time is {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}')
            logging.info(f"Skipping {email} as it already exists in apollo_search_data with 'completed' status")
            print(f'Last execution was on {existing_row['last_execution']} for email {email} and current time is {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}')
            print(f"Skipping {email} as it already exists in apollo_search_data with 'completed' status")
            condition1 = True

    condition2 = False
    if not apollo_credits_data.empty and email in apollo_credits_data['email'].values:
        existing_row = apollo_credits_data[apollo_credits_data['email'] == email].iloc[0]
        if (existing_row['status'] == 'completed') and (pd.to_datetime(existing_row['last_execution']) > (datetime.now() - timedelta(hours=hours_to_check))):
            print(f"Skipping {email} as it already exists in apollo_credits_data with 'completed' status")
            logging.info(f"Skipping {email} as it already exists in apollo_search_data with 'completed' status")
            condition2 = True

    condition3 = False
    if not apollo_upload_data.empty and email in apollo_upload_data['email'].values:
        existing_row = apollo_upload_data[apollo_upload_data['email'] == email].iloc[0]
        if (existing_row['status'] == 'completed') and (pd.to_datetime(existing_row['last_execution']) > (datetime.now() - timedelta(hours=hours_to_check))):
            print(f"Skipping {email} as it already exists in apollo_upload_data with 'completed' status")
            logging.info(f"Skipping {email} as it already exists in apollo_search_data with 'completed' status")
            condition3 = True


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

    # if (condition2 and condition4) :
    #     print(f"Skipping {email} as it already exists in all three tables with 'completed' status")
    #     logging.info(f"Skipping {email} as it already exists in all three tables with 'completed' status")
    #     continue
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
        'sixth_month_credits': 0
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
        options = webdriver.ChromeOptions()

        # --- Stealth / anti-detection tweaks ---
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        hardening_flags = [
            "--disable-blink-features=AutomationControlled",
            "--disable-extensions",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-infobars",
            "--disable-features=VizDisplayCompositor",
            # "--remote-debugging-port=9222",
            # "--headless=new"
        ]
        for flag in hardening_flags:
            options.add_argument(flag)

        # Fake a realistic Chrome UA
        ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/118.0.0.0 Safari/537.36"
        )
        options.add_argument(f"--user-agent={ua}")
        # options.add_argument("--incognito")
        options.add_argument("--disable-web-security")

        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )

        # Stealth tweaks in browser
        try:
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            driver.execute_script("""
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
            """)
        except Exception:
            pass

        wait = WebDriverWait(driver, 20)

        driver.get("https://app.apollo.io/#/login")
        time.sleep(10)

        if row["Type"].lower() == "gmail":
            wait.until(EC.visibility_of_element_located((By.XPATH, "//button[contains(., 'Log In with Google')]"))).click()
            time.sleep(10)

            email_input = wait.until(EC.element_to_be_clickable((By.ID, "identifierId")))
            email_input.clear()
            email_input.send_keys(email)
            email_input.send_keys(Keys.ENTER)
            time.sleep(10)

            password_input = wait.until(EC.element_to_be_clickable((By.NAME, "Passwd")))
            password_input.clear()
            password_input.send_keys(row["Password"])
            password_input.send_keys(Keys.ENTER)
            time.sleep(10)

            wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
            driver.get("https://app.apollo.io/#/settings/credits/current")
            time.sleep(10)
            print('Got the landing page')
            body_txt = driver.find_element(By.TAG_NAME, "body").text.lower()
            print('got body text')
            logout_keywords = ["logged out", "logged you out", "security reasons", "multiple places", "log in"]
            if any(k in body_txt for k in logout_keywords) or "login" in driver.current_url.lower():
                 print('founf forced logout keyword')
                 raise Exception("Apollo forced logout detected")
        else:
            wait.until(EC.visibility_of_element_located((By.NAME, "email"))).send_keys(email)
            time.sleep(1)
            wait.until(EC.visibility_of_element_located((By.NAME, "password"))).send_keys(row["Password"])
            time.sleep(1)

            wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']"))).click()
            time.sleep(7)

            wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
            driver.get("https://app.apollo.io/#/settings/credits/current")
            time.sleep(2)
    except Exception as e:
        print("Driver doesn't initiated")
        if detect_force_logout(driver):
            if driver:
                driver.quit()
            # raise Exception('Apollo Forced login detected on this page')
        time.sleep(10)
        safe_quit(driver)
        time.sleep(20)
        continue
    if driver:
        print('Driver is started')
    condition2  = False
    if not True:

        try:
            page_text = driver.find_element(By.TAG_NAME, 'body').text

            credits_pattern = r'\b(\d+[\d,]*)\s+of\s+(\d+[\d,]*)\s+(emails)\s*/\s*mo\b'
            renewal_pattern = r'Estimated Credit Renewal on:\s+(\w+ \d+, \d{4} \d+:\d+ \w{2})'

            credits_search = re.search(credits_pattern, page_text, re.IGNORECASE)
            renewal_search = re.search(renewal_pattern, page_text)

            if credits_search:
                used_credits, total_credits, unit = credits_search.groups()
                used_credits = int(used_credits.replace(',', '').replace(" ", ""))
                total_credits = int(total_credits.replace(',', '').replace(" ", ""))
            else:
                used_credits = 0
                total_credits = 0

            if renewal_search:
                renewal_date = renewal_search.group(1)
                renewal_date = datetime.strptime(renewal_date, '%b %d, %Y %I:%M %p')
            else:
                renewal_date = None

            print(used_credits, total_credits, renewal_date)
            try:
                navigate_saved_searches()

                titles = []
                icon_elements = driver.find_elements(By.XPATH, "//i[contains(@class, 'mdi-pin')]")

                for element in icon_elements:
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

                searches = dict()
                netnew = dict()
                for title in titles:
                    try:
                        searches[title] = 0
                        netnew[title] = 0
                        xpath_expression = f"(//span[contains(., '{title}')])[1]"
                        title_div = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_expression)))
                        title_div.click()
                        time.sleep(2)

                        saved_links = driver.find_elements(By.XPATH, "//a[contains(@class, 'zp-link')]")
                        for link in saved_links:
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
                        navigate_saved_searches()
                    except Exception as e:
                        # update_tracker_failed(email, 'failed')
                        apollo_credits_data['status'] = 'failed'
                        apollo_search_field['failed_reason'] = str(e)
                        navigate_saved_searches()
            except:
                navigate_saved_searches2()
                searches = dict()
                netnew = dict()
                titles = ['Net New', 'Saved']

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

                for i in range(len(view_options)):
                    print(i)
                    try:
                        view_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@data-name='views']")))
                        view_button.click()
                        time.sleep(1)

                        your_views_tab = wait.until(EC.element_to_be_clickable((By.ID, "private")))
                        your_views_tab.click()
                        time.sleep(1)

                        view_options = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//div[@role='option']")))
                        view_option_text = view_options[i].text

                        view_options[i].click()
                        time.sleep(6)

                        for title in titles:
                            print(f"##### Extracting for {title} #####")
                            try:
                                xpath_expression = f"//div[label[contains(., '{title}')]]//span[contains(text(), 'M') or contains(text(), 'K') or text() != '']"
                                count_element = wait.until(EC.presence_of_element_located((By.XPATH, xpath_expression)))

                                count_value = count_element.text.strip()
                                print(f"Extracted count for {title}: {count_value}")

                                if count_value[-1].lower() == 'k':
                                    count_value = float(count_value[:-1]) * 1000
                                elif count_value[-1].lower() == 'm':
                                    count_value = float(count_value[:-1]) * 1000000
                                else:
                                    count_value = float(count_value)

                                if title == "Net New":
                                    netnew[view_option_text] = count_value
                                else:
                                    searches[view_option_text] = count_value

                                time.sleep(2)

                            except Exception as e:
                                print(f"An error occurred while extracting data for title '{title}': {e}")

                    except Exception as e:
                        print(f"An error occurred while processing the view option {i}: {e}")

        
            print('\n\n')
            print('Reached here\n\n')
            apollo_search_field['status'] = 'completed'
            apollo_search_field['last_execution'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            apollo_search_field['used_credits'] = used_credits
            apollo_search_field['total_credits'] = total_credits
            apollo_search_field['renews_on'] = renewal_date.strftime('%Y-%m-%d %H:%M:%S')
            apollo_search_field['saved_titles'] = "\n".join(list(searches.keys()))
            apollo_search_field['saved_counts'] = "\n".join([str(int(i)) for i in list(searches.values())]),
            apollo_search_field['total_saved'] = sum(list(searches.values()))
            apollo_search_field['netnew_counts'] = "\n".join([str(int(i)) for i in list(netnew.values())])
            apollo_search_field['total_netnew'] = sum(list(netnew.values()))
            # driver.quit()
            time.sleep(2)

        except Exception as e:
            apollo_search_field['status'] = 'failed'
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
    if not True:

        try:
            # soup = BeautifulSoup(driver.page_source, "html.parser")
            time.sleep(20)
            print('going to credits\n\n')
            driver.get("https://app.apollo.io/#/settings/credits/current")
            time.sleep(7 + random.uniform(-1, 2))  # wait for page load

            # Parse the page source
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, "html.parser")

            # 1) Option A: Search the entire text for 'Estimated Credit Renewal on:'
            page_text = soup.get_text()
            time.sleep(1 + random.uniform(-1, 2))

            # driver.get("https://app.apollo.io/#/settings/credits/current")
            # wait.until(EC.visibility_of_element_located((By.TAG_NAME, 'body')))

            # page_text = driver.find_element(By.TAG_NAME, 'body').text
            renewal_pattern = r'Estimated Credit Renewal on:\s+(\w+ \d+, \d{4} \d+:\d+ \w{2})'
            time.sleep(2 + random.uniform(-1, 2))
            renewal_search = re.search(renewal_pattern, page_text)
            if renewal_search:
                renewal_date = renewal_search.group(1)
                renewal_date = datetime.strptime(renewal_date, '%b %d, %Y %I:%M %p')
            else:
                renewal_date = None

            # print(renewal_date)
            if not renewal_date:
                print('Getting captcha issue', end="\n")
                apollo_credits_field['status'] = 'failed'
                apollo_credits_field['failed_reason'] = 'cloudflare challenge'
                # update_status_for_failure(cursor, db, email, "failed" ,"cloudflare challenge")
                continue 
            dates = get_past_renewal_credit_periods(renewal_date)
            days_to_renew = (renewal_date - datetime.now()) <= timedelta(days=7)  # 5 days = 120hrs
            # print(dates)
            #    
            for min_date, max_date in dates:
                min_date_str = min_date.strftime("%Y-%m-%d")
                max_date_str = max_date.strftime("%Y-%m-%d")
                driver.get(f"https://app.apollo.io/#/settings/credits/history?minDate={min_date_str}&maxDate={max_date_str}")
                time.sleep(5 + random.uniform(-1, 2))

                if detect_force_logout(driver):
                    if driver:
                        driver.quit()
                    # raise Exception("Apollo forced logout detected while fetching history")

                page_source = driver.page_source
                soup = BeautifulSoup(page_source, "html.parser")
                credit_section = soup.find("div", string="Email Credits")
                if credit_section:
                    number_div = credit_section.find_previous_sibling("div")
                    if number_div:
                        credits_used = number_div.get_text().strip()
                        email_credits.append(credits_used)
                    else:
                        email_credits.append(None)
                else:
                    email_credits.append(None)
                time.sleep(2)

            while len(email_credits) < 6:
                email_credits.append(-1)
            email_credits = email_credits[::-1]
            apollo_credits_field['first_month_credits'] = email_credits[0]
            apollo_credits_field['second_month_credits'] = email_credits[1]
            apollo_credits_field['third_month_credits'] = email_credits[2]
            apollo_credits_field['fourth_month_credits'] = email_credits[3]
            apollo_credits_field['fifth_month_credits'] = email_credits[4]
            apollo_credits_field['sixth_month_credits'] = email_credits[5]
            formatted_date = renewal_date.strftime('%d %B %Y, %H:%M:%S')
            apollo_credits_field['renewal_date'] = renewal_date.strftime('%Y-%m-%d %H:%M:%S')
            apollo_credits_field['last_execution'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            apollo_credits_field['status'] = 'completed'
        except Exception as e:
            apollo_credits_field['status'] = 'failed'
            print(f"Error processing {email}: {e}")
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
        
    if True:
        # ========== UPLOAD DATA EXTRACTION ==========
        print(f"\n[UPLOAD DATA] Starting upload data extraction for {email}")
        try:
            link = 'https://app.apollo.io/#/lists?groupBy[]=labelModality&perPage=25&sortByField=updated_at&sortAscending=false'
            print(f"[UPLOAD DATA] Navigating to lists page: {link}")
            driver.get(link)
            time.sleep(7)
            
            # Find all row WebElements first
            print(f"[UPLOAD DATA] Finding row elements...")
            row_elements = driver.find_elements(By.CSS_SELECTOR, "div[role='row']")
            print(f"[UPLOAD DATA] Found {len(row_elements)} row elements")
            time.sleep(5)
            
            # Wait for page to fully load and stabilize
            print(f"[UPLOAD DATA] Waiting for page to stabilize...")
            time.sleep(3)
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            time.sleep(2)
            soup_rows = soup.select("div[role='row']")
            print(f"[UPLOAD DATA] Found {len(soup_rows)} soup rows")
            
            data = []  # Initialize data list here
            
            # Debug: Print first row HTML structure
            if soup_rows:
                print(f"[UPLOAD DATA] DEBUG - First row HTML structure:")
                print(f"[UPLOAD DATA] {soup_rows[0].prettify()[:500]}...")
            
            for j, row in enumerate(soup_rows[:MAX_ROWS_TO_PROCESS]):
                print(f"[UPLOAD DATA] Processing row {j+1}/{MAX_ROWS_TO_PROCESS}")
                
                # Skip header row (first row)
                if j == 0:
                    print(f"[UPLOAD DATA] Row {j+1} - Skipping header row")
                    continue
                
                try:
                    # Extract name - based on actual HTML structure
                    name = ""
                    # Column 1 contains the name in an <a> tag with classes zp_sEcm8 zp_zDpQp zp_vJPW7
                    name_selectors = [
                        "div[aria-colindex='1'] a.zp_sEcm8",  # Primary selector based on your HTML
                        "div[aria-colindex='1'] a",           # Fallback for any link in column 1
                        "a.zp_sEcm8",                         # Direct class selector
                        "a[class*='zp_sEcm8']",               # Partial class match
                        "div[aria-colindex='1'] span",        # Span in column 1
                        "a"                                   # Any link as last resort
                    ]
                    
                    for selector in name_selectors:
                        name_tag = row.select_one(selector)
                        if name_tag:
                            name = name_tag.get_text(strip=True)
                            if name:  # Only use if we got actual text
                                print(f"[UPLOAD DATA] Row {j+1} - Name (using {selector}): {name}")
                                break
                    
                    if not name:
                        # Try to get any text from column 1
                        col1 = row.select_one("div[aria-colindex='1']")
                        if col1:
                            name = col1.get_text(strip=True)
                            if name:
                                print(f"[UPLOAD DATA] Row {j+1} - Name (column 1 text): {name}")
                    
                    if not name:
                        print(f"[UPLOAD DATA] Row {j+1} - Name: (empty - using fallback)")
                        # Last resort: use count as name
                        count_tag = row.select_one("div[aria-colindex='2'] span.zp_PTp8r")
                        if count_tag:
                            count_text = count_tag.get_text(strip=True)
                            if count_text:
                                name = f"Upload_{count_text}"
                                print(f"[UPLOAD DATA] Row {j+1} - Name (count-based): {name}")
                    
                    time.sleep(1)

                    # Extract count (if present) - Column 2
                    count_selectors = [
                        "div[aria-colindex='2'] span.zp_PTp8r",  # Primary selector based on your HTML
                        "div[aria-colindex='2'] span",           # Fallback for any span in column 2
                        "span.zp_PTp8r"                          # Direct class selector as last resort
                    ]
                    
                    count = ""
                    for selector in count_selectors:
                        count_tag = row.select_one(selector)
                        if count_tag:
                            count = count_tag.get_text(strip=True)
                            if count:
                                print(f"[UPLOAD DATA] Row {j+1} - Count (using {selector}): {count}")
                                break
                    
                    if not count:
                        print(f"[UPLOAD DATA] Row {j+1} - Count: (empty)")
                    
                    time.sleep(1)

                    # Extract visible date - Column 5 (same as full date column)
                    visible_date_selectors = [
                        "div[aria-colindex='5'] span.zp_PTp8r",  # Primary selector based on your HTML
                        "div[aria-colindex='5'] span",           # Fallback for any span in column 5
                        "span.zp_PTp8r"                          # Direct class selector as last resort
                    ]
                    
                    visible_date = ""
                    for selector in visible_date_selectors:
                        date_tag = row.select_one(selector)
                        if date_tag:
                            visible_date = date_tag.get_text(strip=True)
                            if visible_date:
                                print(f"[UPLOAD DATA] Row {j+1} - Visible Date (using {selector}): {visible_date}")
                                break
                    
                    if not visible_date:
                        print(f"[UPLOAD DATA] Row {j+1} - Visible Date: (empty)")
                    
                    # Debug: Check what we're getting from different columns
                    col3_text = ""
                    col5_text = ""
                    try:
                        col3_elem = row.select_one("div[aria-colindex='3'] span")
                        if col3_elem:
                            col3_text = col3_elem.get_text(strip=True)
                        
                        col5_elem = row.select_one("div[aria-colindex='5'] span")
                        if col5_elem:
                            col5_text = col5_elem.get_text(strip=True)
                        
                        print(f"[UPLOAD DATA] Row {j+1} - DEBUG - Col3: '{col3_text}', Col5: '{col5_text}'")
                    except:
                        pass
                    
                    time.sleep(1)

                    # Now extract full date via Selenium hover - Column 5
                    full_date = ""
                    try:
                        # Find the tooltip trigger element in column 5
                        date_elem = None
                        
                        # Try to find the tooltip element
                        try:
                            date_elem = row_elements[j].find_element(By.CSS_SELECTOR, "div[aria-colindex='5'] span.zp_zGsR3")
                            # date_elem = row_elements[j].find_element(By.CSS_SELECTOR, "div[aria-colindex='5'] span[data-has-tooltip='true']")
                        except:
                            try:
                                date_elem = row_elements[j].find_element(By.CSS_SELECTOR, "div[aria-colindex='5'] span[data-has-tooltip='true']")
                                # date_elem = row_elements[j].find_element(By.CSS_SELECTOR, "div[aria-colindex='5'] span.zp_zGsR3")
                            except:
                                try:
                                    date_elem = row_elements[j].find_element(By.CSS_SELECTOR, "div[aria-colindex='5'] span")
                                except:
                                    pass
                        
                        if date_elem:
                            # Scroll element into view
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", date_elem)
                            time.sleep(1)
                            
                            # Try hover approach only (no clicking to avoid interception)
                            try:
                                # Move to element and hover
                                ActionChains(driver).move_to_element(date_elem).perform()
                                time.sleep(2)
                                
                                # Check for tooltip ID
                                tooltip_id = date_elem.get_attribute("aria-describedby")
                                if tooltip_id:
                                    tooltip_elem = driver.find_element(By.ID, tooltip_id)
                                    full_date = tooltip_elem.text.strip()
                                    if full_date:
                                        print(f"[UPLOAD DATA] Row {j+1} - Full Date: {full_date}")
                                    else:
                                        print(f"[UPLOAD DATA] Row {j+1} - Tooltip found but empty")
                                else:
                                    print(f"[UPLOAD DATA] Row {j+1} - No tooltip ID found after hover")
                            except Exception as e:
                                print(f"[UPLOAD DATA] Row {j+1} - Hover failed: {e}")
                                
                                # Fallback: Try JavaScript hover simulation
                                try:
                                    driver.execute_script("""
                                        var element = arguments[0];
                                        var event = new MouseEvent('mouseover', {
                                            'view': window,
                                            'bubbles': true,
                                            'cancelable': true
                                        });
                                        element.dispatchEvent(event);
                                    """, date_elem)
                                    time.sleep(2)
                                    
                                    tooltip_id = date_elem.get_attribute("aria-describedby")
                                    if tooltip_id:
                                        tooltip_elem = driver.find_element(By.ID, tooltip_id)
                                        full_date = tooltip_elem.text.strip()
                                        if full_date:
                                            print(f"[UPLOAD DATA] Row {j+1} - Full Date (JS hover): {full_date}")
                                except Exception as js_e:
                                    print(f"[UPLOAD DATA] Row {j+1} - JS hover also failed: {js_e}")
                        else:
                            print(f"[UPLOAD DATA] Row {j+1} - Could not find tooltip trigger element")
                            
                    except Exception as hover_e:
                        print(f"[UPLOAD DATA] Row {j+1} - Tooltip extraction error: {hover_e}")

                    # Skip invalid entries (header-like data)
                    # Only check for actual header values, not "People" which is valid data
                    if (name in ["List name", "# of Records", "Type"] or 
                        count in ["# of Records", "Type"] or
                        visible_date in ["Type"]):
                        print(f"[UPLOAD DATA] Row {j+1} - Skipping invalid entry (header-like data)")
                        continue
                    
                    # Always add data, even if name is empty
                    if not name:
                        name = f"Upload_{j+1}"  # Use row number as fallback name
                        print(f"[UPLOAD DATA] Row {j+1} - Using fallback name: {name}")
                    
                    temp_filed = {
                        "name": name,
                        "count": count,
                        "date_visible": visible_date,
                        "date_full": full_date
                    }
                    data.append(temp_filed)
                    print(f"[UPLOAD DATA] Row {j+1} - Added to data: {temp_filed}")
                    
                    # Add sleep between rows to avoid overwhelming the page
                    time.sleep(random.uniform(2, 3))

                except Exception as e:
                    print(f"[UPLOAD DATA] Row {j+1} - Parsing error: {e}")
                    # Still add sleep even on error
                    time.sleep(random.uniform(2, 3))
            
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
            print(f"[UPLOAD DATA] Error processing {email}: {e}")
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
            
            upload_df = pd.DataFrame(processed_records)
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
            
            # Group by month and sum counts
            monthly_data = recent_data.groupby('year_month').agg({
                'count': 'sum',
                'date': 'max'  # Get the latest date in each month
            }).reset_index()
            
            # Ensure all target months are included, even with 0 counts
            monthly_breakdown = []
            for month_period in target_months:
                # Check if this month has data
                month_data = monthly_data[monthly_data['year_month'] == month_period]
                
                if len(month_data) > 0:
                    # Month has data
                    row = month_data.iloc[0]
                    count = int(row['count'])
                    latest_date = row['date'].strftime('%Y-%m-%d %H:%M:%S')
                else:
                    # Month has no data - set to 0
                    count = 0
                    latest_date = None
                
                month_str = month_period.strftime('%Y-%m')  # e.g., '2025-10'
                month_name = month_period.strftime('%b %Y')  # e.g., 'Oct 2025'
                
                monthly_breakdown.append({
                    'year_month': month_str,
                    'month_name': month_name,
                    'count': count,
                    'latest_date': latest_date
                })
            
            print(f"[DATA PROCESSING] Monthly breakdown (all {MONTHS_TO_INCLUDE} months): {monthly_breakdown}")
            
            # ========== LAST UPLOADED DATA COUNT CALCULATION ==========
            # Apply the same logic as sk_test.py to get recent uploaded data count
            print(f"[DATA PROCESSING] Calculating last_uploaded_data count using grouping logic...")
            
            # Filter out monthly and email data for last_uploaded_data calculation
            filtered_records = processed_records.copy()
            
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
                    if not is_already_grouped and row['count'] >= 10000:
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