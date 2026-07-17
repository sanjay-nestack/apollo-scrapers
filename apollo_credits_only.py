import os
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.action_chains import ActionChains
from bs4 import BeautifulSoup
# import mysql.connector, time
import pandas as pd
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import random, re
import time
# from send_whatsapp_msg import send_whatsapp_message_buisness_api, send_crm_data_alert, send_apollo_upload_alert
# import logging

# logging.basicConfig(
#     filename='apollo_upload_log.log',
#     level=logging.INFO,
#     format='%(asctime)s - %(levelname)s - %(message)s',
#     filemode='a'
# )

# db = mysql.connector.connect(
#     host="localhost",
#     user="root",
#     password="",
#     database="crawler_db"
# )
# cursor = db.cursor(dictionary=True)
# print("Database connection established.")

def update_months_and_last_update_and_renew(cursor, db, email, email_credits, renewal_date):
    try:
        sql = """
            INSERT INTO apollo_tracker 
                (email, month_1, month_2, month_3, month_4, month_5, month_6, last_updated_sm, renews_on)
            VALUES 
                (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                month_1 = VALUES(month_1),
                month_2 = VALUES(month_2),
                month_3 = VALUES(month_3),
                month_4 = VALUES(month_4),
                month_5 = VALUES(month_5),
                month_6 = VALUES(month_6),
                last_updated_sm = VALUES(last_updated_sm),
                renews_on = VALUES(renews_on)
        """
        credits = []
        for credit in email_credits:
            try:
                credits.append(int(credit))
            except (ValueError, TypeError):
                credits.append(None)
        while len(credits) < 6:
            credits.append(None)

        # Update apollo_tracker
        cursor.execute(sql, (email, *credits, datetime.now(), renewal_date))
        
        # Update apollo_credit 
        cursor.execute("""
            INSERT INTO apollo_credit (email, renews_on) 
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE
            renews_on = VALUES(renews_on)
        """, (email, renewal_date))

        db.commit()
        print(f"Database updated for {email} with credits: {credits}")
    except Exception as e:
        update_status(email, 'failed', str(e))
        print(f"Database update error for {email}: {e}")


def update_status(cursor, db, email, status, failed_reason=None):
    try:
        sql = """
            INSERT INTO apollo_tracker (email, status_sm, failed_reason)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
            status_sm = VALUES(status_sm),
            failed_reason = VALUES(failed_reason)
        """
        cursor.execute(sql, (email, status, failed_reason))
        db.commit()
        print(f"Status updated for {email} to: {status}. Reason: {failed_reason if failed_reason else 'None'}")
    except Exception as e:
        print(f"Status update error for {email}: {e}")

def update_status_for_failure(cursor, db, email, status, failed_reason=None):
    try:
        sql = """
            INSERT INTO apollo_tracker (email, status_sm, last_updated_sm, failed_reason)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            status_sm = VALUES(status_sm),
            last_updated_sm = VALUES(last_updated_sm),
            failed_reason = VALUES(failed_reason)
        """
        cursor.execute(sql, (email, status, datetime.now(), failed_reason))
        db.commit()
        print(f"Status updated for {email} to: {status}. Reason: {failed_reason if failed_reason else 'None'}")
    except Exception as e:
        print(f"Status update error for {email}: {e}")

# def get_renewal_date(email):
#     try:
#         cursor.execute("""
#             SELECT renews_on FROM apollo_credit WHERE email = %s
#         """, (email,))
#         result = cursor.fetchone()
#         if result:
#             renewal_date = result[0]
#             print(f"Renewal date for {email} retrieved from database: {renewal_date}")
#             return renewal_date
#         else:
#             print(f"No renewal date found for {email} in apollo_credit table")
#             return None
#     except Exception as e:
#         print(f"Database query error for {email} when retrieving renewal date: {e}")
#         return None
    
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

def get_and_save_email_credits():

    sheet_url = "https://docs.google.com/spreadsheets/d/1kKqEfKLSW9cUtcjmNlinxeYXt-EtcXm5B5c4m7_CnbI/export?format=csv&gid=0"
    df = pd.read_csv(sheet_url)
    print("Sheet data loaded successfully.")

    active_emails = df['Email'].to_list()
    # in_clause = ", ".join(f"'{email}'" for email in active_emails)

    # sql_deactivate_others = f"""
    # UPDATE apollo_tracker
    # SET is_active = 0
    # WHERE email NOT IN ({in_clause});
    # """

    # sql_activate_list = f"""
    # UPDATE apollo_tracker
    # SET is_active = 1
    # WHERE email IN ({in_clause});
    # """
    # cursor.execute(sql_deactivate_others)
    # cursor.execute(sql_activate_list)

    # db.commit()
    # print("Database sync complete.")

    receivers_number_list = [
        '+918079010022', #Sanjay
        '+919121746330', # Vijay Sir
        '+918008513071', # Varuna
        '+919847096264',  #Rahul
    ]

    i = 0

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
    if os.path.exists('apollo_credits_only.csv'):
        apollo_data = pd.read_csv(
            'apollo_credits_only.csv',
            names=columns_apollo_credits,
            header=None,  # tells pandas the file has no header row
        )
    else:
        apollo_data = pd.DataFrame(columns=columns_apollo_credits)

    
    for index, row in df.iterrows():
        print(f'starting for {i}')
        i += 1
        email = row["Email"]
        
        if len(apollo_data) > 0:        
            if email in apollo_data['email'].to_list():
                print(f"Skipping {email} as it already exists in the apollo_data")
                continue
        print(f"Starting process for {email}")

        # cursor.execute("""
        #     SELECT status_sm, last_updated_sm FROM apollo_tracker WHERE email = %s
        # """, (email,))
        # result = cursor.fetchone()
        
        # if result:
        #     status, last_updated = result['status_sm'], result['last_updated_sm']
        #     print(type(last_updated), last_updated)
        #     hours_for_check = 24
        #     if (status != 'failed') and (last_updated is not None) and ((datetime.now() - last_updated) <= timedelta(hours=hours_for_check)):
        #         print(f"{email} - Status not 'failed' and last update was less than {hours_for_check} hours ago. Skipping.")
        #         continue
        #     elif status == 'failed':
        #         print(f"{email} - Status is 'failed'. Proceeding with further checks.")
        # else:
        #     print(f"{email} - No entry in apollo_tracker. Proceeding with processing.")

        email_credits = []
        driver = None
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
            # options = webdriver.ChromeOptions()
            # options.add_argument("start-maximized")
            # options.add_argument("--headless")
            # options.add_experimental_option("excludeSwitches", ["enable-automation"])
            # options.add_experimental_option('useAutomationExtension', False)
            # driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
            wait = WebDriverWait(driver, 20)
            print(f"Webdriver initialized for {email}")

            driver.get("https://app.apollo.io/#/login")
            time.sleep(4 + random.uniform(-1, 2))

            if row["Type"].lower() == "gmail":
                wait.until(EC.visibility_of_element_located((By.XPATH, "//button[contains(., 'Log In with Google')]"))).click()
                email_input = wait.until(EC.element_to_be_clickable((By.ID, "identifierId")))
                email_input.clear()
                email_input.send_keys(email)
                email_input.send_keys(Keys.ENTER)
                time.sleep(2 + random.uniform(-1, 2))
                password_input = wait.until(EC.element_to_be_clickable((By.NAME, "Passwd")))
                password_input.clear()
                password_input.send_keys(row["Password"])
                password_input.send_keys(Keys.ENTER)
                time.sleep(7 + random.uniform(-1, 2))
            else:
                wait.until(EC.visibility_of_element_located((By.NAME, "email"))).send_keys(email)
                wait.until(EC.visibility_of_element_located((By.NAME, "password"))).send_keys(row["Password"])
                wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']"))).click()
                time.sleep(7 + random.uniform(-1, 2))

            # ✅ Check for Cloudflare verification or password change and return immediately
            soup = BeautifulSoup(driver.page_source, "html.parser")
            # if "Verify you are human" in soup.get_text() or soup.find(class_="cf-challenge"):
            #     update_status(cursor, db, email, "failed", "Cloudflare verification required")  # Log immediately
            #     print(f"{email} - Cloudflare verification required. Skipping.")
            #     continue  # Stop execution for this email

            # if "password was changed" in soup.get_text():
            #     update_status(cursor, db, email, "failed", "Password changed recently")  # Log immediately
            #     print(f"{email} - Password was changed recently. Skipping.")
            #     continue  # Stop execution for this email

            # if "Wrong password" in soup.get_text():
            #     update_status(cursor, db, email, "failed", "Incorrect password")  # Log immediately
            #     print(f"{email} - Incorrect password. Skipping.")
            #     continue  # Stop execution for this email
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
                filed['status'] = 'failed'
                filed['failed_reason'] = 'cloudflare challenge'
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
            filed['first_month_credits'] = email_credits[0]
            filed['second_month_credits'] = email_credits[1]
            filed['third_month_credits'] = email_credits[2]
            filed['fourth_month_credits'] = email_credits[3]
            filed['fifth_month_credits'] = email_credits[4]
            filed['sixth_month_credits'] = email_credits[5]
            formatted_date = renewal_date.strftime('%d %B %Y, %H:%M:%S')
            filed['renewal_date'] = renewal_date.strftime('%Y-%m-%d %H:%M:%S')
            filed['last_execution'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            filed['status'] = 'completed'

            if days_to_renew and int(email_credits[0]) < 9700:

                template_variables = {
                    '1': f'{email}',  # Email ({{1}})
                    '2': f'{formatted_date}',        # Renewal Date ({{2}})
                    '3': f'{int(email_credits[0])}'                # Credits Used ({{3}})
                }

                # for receiver_number in receivers_number_list:
                #     send_whatsapp_message_buisness_api(receiver_number=receiver_number, template_variables=template_variables)


            else:
                print(f"Renewal date is more than 5 days for {email}")

            # update_months_and_last_update_and_renew(cursor, db, email, email_credits, renewal_date)
            # update_status(cursor, db, email, "completed" ,"")

            # print('')
            # print('email credits ', email_credits)
            # print('')
            temp_df = pd.DataFrame([filed])
            temp_df.to_csv('apollo_credits_only.csv', mode='a', header=not i, index=False)
        except Exception as e:
            print(f"Error processing {email}: {e}")
            # update_status_for_failure(cursor, db, email, "failed", str(e))

        finally:
            if driver:
                driver.quit()
        time.sleep(random.uniform(150, 180))

get_and_save_email_credits()
# if cursor:
#     cursor.close()
# if db:
#     db.close()
