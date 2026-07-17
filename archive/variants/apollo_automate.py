import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# chrome_options = Options()
# chrome_options.add_argument("--disable-blink-features=AutomationControlled")
# chrome_options.add_argument("--incognito")

from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import re, time
import pandas as pd
from datetime import datetime, timedelta

# chrome_options = webdriver.ChromeOptions()
# chrome_options.add_argument("--incognito")

def navigate_saved_searches():
    time.sleep(5)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
    driver.get("https://app.apollo.io/#/people")
    time.sleep(5)

    # wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@href='#/']"))).click()
    # time.sleep(2)
    # driver.refresh()
    # time.sleep(3)
    # wait.until(EC.element_to_be_clickable((By.XPATH, "//div[contains(text(),'People')]"))).click()
    # time.sleep(2)
    wait.until(EC.visibility_of_element_located((By.LINK_TEXT, "Saved searches"))).click()
    time.sleep(5)
    wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Private')]"))).click()
    time.sleep(5)

def navigate_saved_searches2():
    time.sleep(5)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
    driver.get("https://app.apollo.io/#/people")
    time.sleep(5)


sheet_url = "https://docs.google.com/spreadsheets/d/1kKqEfKLSW9cUtcjmNlinxeYXt-EtcXm5B5c4m7_CnbI/export?format=csv&gid=0"
df = pd.read_csv(sheet_url)


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

for index, row in df.iterrows():
    email = row["Email"]

    # If apollo_search_data is not empty and email exists
    condition1 = False
    if not apollo_search_data.empty and email in apollo_search_data['email'].values:
        existing_row = apollo_search_data[apollo_search_data['email'] == email].iloc[0]

        if existing_row['status'] == 'completed':
            print(f"Skipping {email} as it already exists in apollo_search_data with 'completed' status")
            condition1 = True

    condition2 = False
    if not apollo_credits_data.empty and email in apollo_credits_data['email'].values:
        existing_row = apollo_credits_data[apollo_credits_data['email'] == email].iloc[0]
        if existing_row['status'] == 'completed':
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
    filed = {
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
    
    driver = None
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
        options.add_argument("--incognito")
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
        time.sleep(1)

        if row["Type"].lower() == "gmail":
            wait.until(EC.visibility_of_element_located((By.XPATH, "//button[contains(., 'Log In with Google')]"))).click()
            time.sleep(2)

            email_input = wait.until(EC.element_to_be_clickable((By.ID, "identifierId")))
            email_input.clear()
            email_input.send_keys(email)
            email_input.send_keys(Keys.ENTER)
            time.sleep(2)

            password_input = wait.until(EC.element_to_be_clickable((By.NAME, "Passwd")))
            password_input.clear()
            password_input.send_keys(row["Password"])
            password_input.send_keys(Keys.ENTER)
            time.sleep(7)

            wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
            driver.get("https://app.apollo.io/#/settings/credits/current")
            time.sleep(5)
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

        # wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-cy='user-profile']"))).click()
        # time.sleep(2)

        # wait.until(EC.element_to_be_clickable((By.XPATH, "//span[contains(text(),'View credit usage')]"))).click()
        # time.sleep(2)
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

            # cursor.execute("""
            # INSERT INTO apollo_credit (email, used_credits, total_credits, renews_on, saved_titles, saved_counts, total_saved, netnew_counts, total_netnew) 
            # VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            # ON DUPLICATE KEY UPDATE
            # used_credits = VALUES(used_credits), total_credits = VALUES(total_credits), renews_on = VALUES(renews_on), saved_titles = VALUES(saved_titles), saved_counts = VALUES(saved_counts), total_saved = VALUES(total_saved), netnew_counts = VALUES(netnew_counts), total_netnew = VALUES(total_netnew), updated_at = CURRENT_TIMESTAMP()
            # """, (
            #     email, used_credits, total_credits, renewal_date,
            #     "\n".join(list(searches.keys())),
            #     "\n".join([str(int(i)) for i in list(searches.values())]),
            #     sum(list(searches.values())),
            #     "\n".join([str(int(i)) for i in list(netnew.values())]),
            #     sum(list(netnew.values()))
            # ))
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
            driver.quit()
            time.sleep(2)

        except Exception as e:
            apollo_search_field['status'] = 'failed'
        # data_field['failed_reason'] = str(e)
        csv_path = r'C:\Users\Test\Desktop\apollo_scraper\apollo_search_data.csv'
        new_entry = pd.DataFrame([apollo_search_field])  # `data_field` is a dict with the new row

        # Step 1: Load existing CSV (if it exists)
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)

            # Step 2: Remove rows with same email as new entry
            df = df[df['email'] != apollo_search_field['email']]

            # Step 3: Append new entry
            df = pd.concat([df, new_entry], ignore_index=True)
        else:
            # First time creating the file
            df = new_entry
        df.to_csv(csv_path, index=False)

    if not condition2:
        pass

    if driver:
        driver.quit()
    time.sleep(150)

print("Extracted All Apollo Account Data. Please Close This Window")