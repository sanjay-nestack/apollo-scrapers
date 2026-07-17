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

access_key = os.getenv('AWS_ACCESS_KEY', '')
secret_key = os.getenv('AWS_SECRET_KEY', '')

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
if os.path.exists(r'C:\Users\Test\Desktop\apollo_scraper\apollo_search_data.csv'):
    apollo_search_data = pd.read_csv(
        'apollo_search_data.csv',
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
    'first_month',
    'second_month',
    'third_month',
    'fourth_month',
    'fifth_month',
    'sixth_month'
    ]
if os.path.exists(r'C:\Users\Test\Desktop\apollo_scraper\apollo_credits_only.csv'):
    apollo_credits_data = pd.read_csv(
        r'C:\Users\Test\Desktop\apollo_scraper\apollo_credits_only.csv',
        names=columns_apollo_credits,
        header=None,  # tells pandas the file has no header row
    )
else:
    apollo_credits_data = pd.DataFrame(columns=columns_apollo_credits)

apollo_upload_details = []
apollo_credits_data['renewal_date'] = pd.to_datetime(apollo_credits_data['renewal_date'], errors='coerce', format='%Y-%m-%d %H:%M:%S')
final_df = pd.merge(df, apollo_credits_data, left_on='Email', right_on='email', how='left')
final_df_sorted = final_df.sort_values(by='renewal_date', ascending=True)

for index, row in final_df_sorted.iterrows():
    email = row["Email"]

    # if email != 'jith@nestack.info':
    #     continue
    # if (row['renewal_date'] is not None) and (row['renewal_date'] > (datetime.now() + timedelta(days=10))):
    #     print(f"{email} - Renewal date is more than 10 days from now. Skipping.")
    #     continue

    # If apollo_search_data is not empty and email exists
    condition1 = False
    if not apollo_search_data.empty and email in apollo_search_data['email'].values:
        existing_row = apollo_search_data[apollo_search_data['email'] == email].iloc[0]

        if (existing_row['status'] == 'completed') and (pd.to_datetime(existing_row['last_execution']) > (datetime.now() - timedelta(hours=20))):
            print(f"Skipping {email} as it already exists in apollo_search_data with 'completed' status")
            condition1 = True

    condition2 = False
    if not apollo_credits_data.empty and email in apollo_credits_data['email'].values:
        existing_row = apollo_credits_data[apollo_credits_data['email'] == email].iloc[0]
        if (existing_row['status'] == 'completed') and (pd.to_datetime(existing_row['last_execution']) > (datetime.now() - timedelta(hours=20))):
            print(f"Skipping {email} as it already exists in apollo_credits_data with 'completed' status")
            condition2 = True

    if condition1 and condition2:
        print(f"Skipping {email} as it already exists in both apollo_search_data and apollo_credits_data with 'completed' status")
        continue

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
            "--remote-debugging-port=9222",
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
            body_txt = driver.find_element(By.TAG_NAME, "body").text.lower()
            logout_keywords = ["logged out", "logged you out", "security reasons", "multiple places", "log in"]
            if any(k in body_txt for k in logout_keywords) or "login" in driver.current_url.lower():
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

    if not condition1:

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
        csv_path = r'C:\Users\Test\Desktop\apollo_scraper\apollo_search_data.csv'
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
        df.to_csv(csv_path, index=False)

    email_credits = []
    if not condition2:

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
        csv_path_credits = r'C:\Users\Test\Desktop\apollo_scraper\apollo_credits_only.csv'
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
        df_credits.to_csv(csv_path_credits, index=False)
        time.sleep(random.uniform(20, 30))
        
        # try:
        #     link = 'https://app.apollo.io/#/lists?groupBy[]=labelModality&perPage=25&sortByField=updated_at&sortAscending=false'
        #     driver.get(link)
        #     time.sleep(7)
            
            
        #     # Find all row WebElements first
        #     row_elements = driver.find_elements(By.CSS_SELECTOR, "div[role='row']")
        #     time.sleep(7)
        #     soup = BeautifulSoup(driver.page_source, 'html.parser')
        #     time.sleep(2)
        #     soup_rows = soup.select("div[role='row']")
            
        #     for j, row in enumerate(soup_rows[:15]):
        #         try:
        #             # Extract name
        #             name_tag = row.select_one("a.zp_p2Xqs")
        #             name = name_tag.get_text(strip=True) if name_tag else ""
        #             time.sleep(2)

        #             # Extract count (if present)
        #             count_tag = row.select_one("span.zp_PTp8r")
        #             time.sleep(2)
        #             count = count_tag.get_text(strip=True) if count_tag else ""

        #             # Extract visible date
        #             date_tag = row.select_one("span.zp_zGsR3")
        #             visible_date = date_tag.get_text(strip=True) if date_tag else ""
        #             time.sleep(3)

        #             # Now extract full date via Selenium hover
        #             full_date = ""
        #             try:
        #                 # Selenium match for the same index
        #                 date_elem = row_elements[j].find_element(By.CSS_SELECTOR, "span.zp_zGsR3")
        #                 time.sleep(5)
        #                 ActionChains(driver).move_to_element(date_elem).perform()
        #                 time.sleep(7)

        #                 tooltip_id = date_elem.get_attribute("aria-describedby")
        #                 if tooltip_id:
        #                     tooltip_elem = driver.find_element(By.ID, tooltip_id)
        #                     full_date = tooltip_elem.text.strip()
                            
        #             except Exception as hover_e:
        #                 print(f"[!] Tooltip issue on row {j}: {hover_e}")

        #             if name:
        #                 temp_filed = {
        #                     "name": name,
        #                     "count": count,
        #                     "date_visible": visible_date,
        #                     "date_full": full_date
        #                 }
        #                 data.append(temp_filed)
        #                 # print(temp_filed)

        #         except Exception as e:
        #             print(f"[!] Parsing error on row {j}: {e}")
        #     if len(data)>0 and all(d['date_full'] != '' for d in data):
        #         apollo_upload_filed["status"] = 'success'
        #     else:  
        #         apollo_upload_filed["status"] = 'failed'
        # except Exception as e:
        #     print(f"Error processing {email}: {e}")
        #     apollo_upload_filed["data"] = data
        #     apollo_upload_filed['last_execution'] = datetime.now()
        #     apollo_upload_details.append(apollo_upload_filed)
            
        # if len(apollo_upload_filed['data']) > 0 and apollo_upload_filed['status'] == 'success' and all(d['date_full'] != '' for d in apollo_upload_filed['data']):
        #     records = apollo_upload_filed['data'].copy()
        #     today = datetime.now()
        #     upload_df = pd.DataFrame([
        #         {
        #             'name': r['name'],
        #             'count': convert_count(r['count']),
        #             'date': convert_date(r['date_full'])
        #         }
        #         for r in records
        #         if 'monthly' not in r['name'].lower() and '@' not in r['name']
        #     ])
        #     upload_df = upload_df.sort_values(by='date', ascending=False).reset_index(drop=True)
        #     groups = []
        #     current_group = []

        #     for i, row in upload_df.iterrows():
        #         if row['count'] < 1000:
        #             continue

        #         if not current_group:
        #             current_group.append(row)
        #         else:
        #             last_date = current_group[-1]['date']
        #             if abs((row['date'] - last_date).days) <= 1:
        #                 current_group.append(row)
        #             else:
        #                 groups.append(current_group)
        #                 current_group = [row]

        #     if current_group:
        #         groups.append(current_group)

        #     # Apply second rule: look for solo uploads with ≥10K
        #     for i, row in upload_df.iterrows():
        #         is_already_grouped = any(row['name'] in [r['name'] for r in g] for g in groups)
        #         if not is_already_grouped and row['count'] >= 10000:
        #             groups.append([row])

        #     usable_data_list = groups[0]
        #     total_count = 0
        #     date_list = []
        #     for usable_data in usable_data_list:
        #         total_count += usable_data['count']
        #         date_list.append(usable_data['date'])
        #     last_uploaded_date = max(date_list)
        # else:
        #     total_count = 0
        #     last_uploaded_date = apollo_upload_filed['last_execution']
        # final_filed = {
        #     'email' : apollo_upload_filed['email'],
        #     'data_count' : total_count,
        #     'last_uploaded' : last_uploaded_date,
        #     'status' : apollo_upload_filed['status'],
        #     'last_execution' : apollo_upload_filed['last_execution']
        # }
        # temp_upload_df = pd.DataFrame([final_filed])
        # if os.path.exists(r'C:\Users\Test\Desktop\apollo_scraper\apollo_upload_data_append.csv'):
        #     try:
        #         temp_upload_df1 = pd.read_csv(r'C:\Users\Test\Desktop\apollo_scraper\apollo_upload_data_append.csv')
        #         temp_upload_df1 = temp_upload_df1[temp_upload_df1['email'] != final_filed['email']]
        #     except:
        #         temp_upload_df1 = pd.DataFrame()
        #     temp_upload_df = pd.concat([temp_upload_df, temp_upload_df1], ignore_index=True)
        #     temp_upload_df.to_csv(r'C:\Users\Test\Desktop\apollo_scraper\apollo_upload_data_append.csv', index=False)
        # else:
        #     temp_upload_df.to_csv(r'C:\Users\Test\Desktop\apollo_scraper\apollo_upload_data_append.csv', index=False)
        # time.sleep(random.uniform(20, 30))

    safe_quit(driver)
    sleep_time = 900
    print(f'Taking break for {sleep_time} seconds.')
    time.sleep(sleep_time)

def convert_count(c):
    c = c.upper().replace(",", "")
    return int(float(c.replace("K", "")) * 1000) if "K" in c else int(c)

def convert_date(dstr):
    return datetime.strptime(dstr, "%b %d, %Y %I:%M %p")

def apollo_upload_data_insertion(all_data):
# Parse and filter
    final_data_list = []
    for data in all_data:
        if len(data['data']) > 0 and data['status'] == 'success' and all(d['date_full'] != '' for d in data['data']):
            records = data['data'].copy()
            today = datetime.now()
            upload_df = pd.DataFrame([
                {
                    'name': r['name'],
                    'count': convert_count(r['count']),
                    'date': convert_date(r['date_full'])
                }
                for r in records
                if 'monthly' not in r['name'].lower() and '@' not in r['name']
            ])
            upload_df = upload_df.sort_values(by='date', ascending=False).reset_index(drop=True)
            groups = []
            current_group = []

            for i, row in upload_df.iterrows():
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
            for i, row in upload_df.iterrows():
                is_already_grouped = any(row['name'] in [r['name'] for r in g] for g in groups)
                if not is_already_grouped and row['count'] >= 10000:
                    groups.append([row])

            usable_data_list = groups[0]
            total_count = 0
            date_list = []
            for usable_data in usable_data_list:
                total_count += usable_data['count']
                date_list.append(usable_data['date'])
            last_uploaded_date = max(date_list)
        else:
            total_count = 0
            last_uploaded_date = data['last_execution']
        final_filed = {
            'email' : data['email'],
            'data_count' : total_count,
            'last_uploaded' : last_uploaded_date,
            'status' : data['status'],
            'last_execution' : data['last_execution']
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

UploadToAWS(r'C:\Users\Test\Desktop\apollo_scraper\apollo_search_data.csv', 'apollo-tables',f'apollo_searches_{timestamp}.csv')
UploadToAWS(r'C:\Users\Test\Desktop\apollo_scraper\apollo_credits_only.csv', 'apollo-tables',f'apollo_credits_{timestamp}.csv')
# UploadToAWS(r'C:\Users\Test\Desktop\apollo_scraper\apollo_upload_data.csv', 'apollo-tables',f'apollo_upload_data_{timestamp}.csv')

print("Uploaded All Apollo Account Data to AWS")
print("Extracted All Apollo Account Data. Please Close This Window")