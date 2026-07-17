from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.action_chains import ActionChains
from bs4 import BeautifulSoup
import mysql.connector, time
import pandas as pd
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import random, re
from send_whatsapp_msg import send_whatsapp_message_buisness_api, send_crm_data_alert, send_apollo_upload_alert
import logging

logging.basicConfig(
    filename='apollo_upload_log.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='a'
)

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="crawler_db"
)
cursor = db.cursor(dictionary=True)
print("Database connection established.")

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
    in_clause = ", ".join(f"'{email}'" for email in active_emails)

    sql_deactivate_others = f"""
    UPDATE apollo_tracker
    SET is_active = 0
    WHERE email NOT IN ({in_clause});
    """

    sql_activate_list = f"""
    UPDATE apollo_tracker
    SET is_active = 1
    WHERE email IN ({in_clause});
    """
    cursor.execute(sql_deactivate_others)
    cursor.execute(sql_activate_list)

    db.commit()
    print("Database sync complete.")

    receivers_number_list = [
        '+918079010022', #Sanjay
        '+919121746330', # Vijay Sir
        '+918008513071', # Varuna
        '+919847096264',  #Rahul
    ]

    i = 1
    all_data = []
    for index, row in df.iterrows():
        print(f'starting for {i}')
        i += 1
        email = row["Email"]
        print(f"Starting process for {email}")

        cursor.execute("""
            SELECT status_sm, last_updated_sm FROM apollo_tracker WHERE email = %s
        """, (email,))
        result = cursor.fetchone()
        
        if result:
            status, last_updated = result['status_sm'], result['last_updated_sm']
            print(type(last_updated), last_updated)
            hours_for_check = 2
            if (status != 'failed') and (last_updated is not None) and ((datetime.now() - last_updated) <= timedelta(hours=hours_for_check)):
                print(f"{email} - Status not 'failed' and last update was less than {hours_for_check} hours ago. Skipping.")
                continue
            elif status == 'failed':
                print(f"{email} - Status is 'failed'. Proceeding with further checks.")
        else:
            print(f"{email} - No entry in apollo_tracker. Proceeding with processing.")

        email_credits = []
        driver = None
        status = 'failed'
        filed = {
            'email': email,
            'data' : [],
            'status': status,
            'last_execution': ''
        }
        data = []
        try:
            options = webdriver.ChromeOptions()
            options.add_argument("start-maximized")
            options.add_argument("--headless")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
            wait = WebDriverWait(driver, 20)
            print(f"Webdriver initialized for {email}")

            driver.get("https://app.apollo.io/#/login")
            time.sleep(1 + random.uniform(-1, 2))

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
            if "Verify you are human" in soup.get_text() or soup.find(class_="cf-challenge"):
                update_status(cursor, db, email, "failed", "Cloudflare verification required")  # Log immediately
                print(f"{email} - Cloudflare verification required. Skipping.")
                continue  # Stop execution for this email

            if "password was changed" in soup.get_text():
                update_status(cursor, db, email, "failed", "Password changed recently")  # Log immediately
                print(f"{email} - Password was changed recently. Skipping.")
                continue  # Stop execution for this email

            if "Wrong password" in soup.get_text():
                update_status(cursor, db, email, "failed", "Incorrect password")  # Log immediately
                print(f"{email} - Incorrect password. Skipping.")
                continue  # Stop execution for this email
            driver.get("https://app.apollo.io/#/settings/credits/current")
            time.sleep(5 + random.uniform(-1, 2))  # wait for page load

            # Parse the page source
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, "html.parser")

            # 1) Option A: Search the entire text for 'Estimated Credit Renewal on:'
            page_text = soup.get_text()

            # driver.get("https://app.apollo.io/#/settings/credits/current")
            # wait.until(EC.visibility_of_element_located((By.TAG_NAME, 'body')))

            # page_text = driver.find_element(By.TAG_NAME, 'body').text
            renewal_pattern = r'Estimated Credit Renewal on:\s+(\w+ \d+, \d{4} \d+:\d+ \w{2})'
            renewal_search = re.search(renewal_pattern, page_text)
            if renewal_search:
                renewal_date = renewal_search.group(1)
                renewal_date = datetime.strptime(renewal_date, '%b %d, %Y %I:%M %p')
            else:
                renewal_date = None

            # print(renewal_date)
            if not renewal_date:
                print('Getting captcha issue', end="\n")
                update_status_for_failure(cursor, db, email, "failed" ,"cloudflare challenge")
                continue 
            dates = get_past_renewal_credit_periods(renewal_date)
            days_to_renew = (renewal_date - datetime.now()) <= timedelta(days=6)  # 5 days = 120hrs
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
                email_credits.append(None)
            email_credits = email_credits[::-1]
            formatted_date = renewal_date.strftime('%d %B %Y, %H:%M:%S')

            if days_to_renew and int(email_credits[0]) < 9700:

                template_variables = {
                    '1': f'{email}',  # Email ({{1}})
                    '2': f'{formatted_date}',        # Renewal Date ({{2}})
                    '3': f'{int(email_credits[0])}'                # Credits Used ({{3}})
                }

                for receiver_number in receivers_number_list:
                    send_whatsapp_message_buisness_api(receiver_number=receiver_number, template_variables=template_variables)


            else:
                print(f"Renewal date is more than 5 days for {email}")

            update_months_and_last_update_and_renew(cursor, db, email, email_credits, renewal_date)
            update_status(cursor, db, email, "completed" ,"")
            link = 'https://app.apollo.io/#/lists?groupBy[]=labelModality&perPage=25&sortByField=updated_at&sortAscending=false'
            driver.get(link)
            time.sleep(7)
            

            # Find all row WebElements first
            row_elements = driver.find_elements(By.CSS_SELECTOR, "div[role='row']")
            time.sleep(7)
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            time.sleep(2)
            soup_rows = soup.select("div[role='row']")
            
            for i, row in enumerate(soup_rows[:15]):
                try:
                    # Extract name
                    name_tag = row.select_one("a.zp_p2Xqs")
                    name = name_tag.get_text(strip=True) if name_tag else ""
                    time.sleep(2)

                    # Extract count (if present)
                    count_tag = row.select_one("span.zp_PTp8r")
                    time.sleep(2)
                    count = count_tag.get_text(strip=True) if count_tag else ""

                    # Extract visible date
                    date_tag = row.select_one("span.zp_zGsR3")
                    visible_date = date_tag.get_text(strip=True) if date_tag else ""
                    time.sleep(3)

                    # Now extract full date via Selenium hover
                    full_date = ""
                    try:
                        # Selenium match for the same index
                        date_elem = row_elements[i].find_element(By.CSS_SELECTOR, "span.zp_zGsR3")
                        time.sleep(5)
                        ActionChains(driver).move_to_element(date_elem).perform()
                        time.sleep(7)

                        tooltip_id = date_elem.get_attribute("aria-describedby")
                        if tooltip_id:
                            tooltip_elem = driver.find_element(By.ID, tooltip_id)
                            full_date = tooltip_elem.text.strip()
                            
                    except Exception as hover_e:
                        print(f"[!] Tooltip issue on row {i}: {hover_e}")

                    if name:
                        temp_filed = {
                            "name": name,
                            "count": count,
                            "date_visible": visible_date,
                            "date_full": full_date
                        }
                        data.append(temp_filed)
                        # print(temp_filed)

                except Exception as e:
                    print(f"[!] Parsing error on row {i}: {e}")
            if len(data)>0 and all(d['date_full'] != '' for d in data):
                status = 'success'
            else:
                status = 'failed'

            # print('')
            # print('email credits ', email_credits)
            # print('')
        except Exception as e:
            print(f"Error processing {email}: {e}")
            update_status_for_failure(cursor, db, email, "failed", "Cloudflare Challenge")
            status = 'failed'

        finally:
            if driver:
                driver.quit()
        filed["data"] = data
        filed["status"] = status
        filed['last_execution'] = datetime.now()
        all_data.append(filed)
        time.sleep(random.uniform(150, 180))

    return all_data



def crm_data_alert():
    cursor.execute("SELECT email, renews_on, month_1, month_2, month_3, month_4, month_5, month_6 FROM apollo_tracker WHERE is_active = 1")
    accounts_6m_credits = cursor.fetchall()

    cursor.execute("SELECT * FROM crm_credits_logs WHERE year = DATE_FORMAT(NOW(), '%Y')")
    crm_credits_logs = cursor.fetchall()

    # Prepare CRM lookup dictionary
    crm_lookup = {detail['email']: detail for detail in crm_credits_logs}
    message_sending_data = []

    for account in accounts_6m_credits:
        try:
            # Parse the renews_on date properly
            renews_on = account['renews_on']
            if isinstance(renews_on, str):
                renews_on = datetime.strptime(renews_on, '%Y-%m-%d')  # Adjust if your DB returns full date strings
            elif isinstance(renews_on, datetime):
                pass  # Already datetime
            else:
                continue  # Skip invalid data

            # Renewal month and previous month
            renewal_month = renews_on.strftime('%b').lower()   # like 'jan'
            previous_month = (renews_on - relativedelta(months=1)).strftime('%b').lower()
            renewal_month_big = renews_on.strftime('%B')
            previous_month_big = (renews_on - relativedelta(months=1)).strftime('%B')

            # Map credits
            mapping_credits = {
                renewal_month: {'actual_name': renewal_month_big, 'credits' : account.get('month_1', 0)},
                previous_month: {'actual_name': previous_month_big, 'credits' :  account.get('month_2', 0)}
            }

            # Check CRM details
            crm_detail = crm_lookup.get(account['email'])
            if not crm_detail:
                continue

            # Validate credits
            for month, credit in mapping_credits.items():

                try:
                    
                    credit_value = int(credit['credits']) if credit['credits'] is not None else 0
                    field = {
                        'email' : account['email'],
                        'renews_on': account['renews_on'],
                        'month' : credit['actual_name'],
                        'credit' : credit_value,
                        'crm' : 0
                    }
                    if credit_value > 9500:
                        months_name = f'{month}_value'
                        if not crm_detail.get(months_name):
                            message_sending_data.append(field)
                            # print(f"Action required for {account['email']} at {month.upper()}")
                            # break  # Notify only once
                except (ValueError, TypeError):
                    continue

        except Exception as e:
            print(f"Error processing account {account['email']}: {e}")

    var_data = ' '.join(
        f"📌 {i+1}. Email: {d['email']}, Apollo Credits: {d['credit']} (for {d['month']} Month)."
        for i, d in enumerate(message_sending_data)
    )

    variables = {
        "1": str(len(message_sending_data)),
        "2": var_data
    }
    receivers_number_list_updated = [
        '+918079010022', #Sanjay
        '+919121746330', # Vijay Sir
        '+919847096264',  #Rahul
    ]

    if len(message_sending_data) > 5:
        for receiver_number in receivers_number_list_updated:
            send_crm_data_alert(receiver_number, variables)
    
    print("DB closed")
    print("Process is complete")

def assign_tag(row):
    now = datetime.now()
    upload_plus_7 = row['last_uploaded'] + timedelta(days=7)

    if now < upload_plus_7:
        return "still_open_room" if row['data_count'] < 70000 else "complete"
    elif upload_plus_7 <= now < (upload_plus_7 + timedelta(days=1)):
        return "open_to_upload"
    elif now >= (upload_plus_7 + timedelta(days=1)):
        return "missed_upload"
    return "unknown"

def convert_count(c):
    c = c.upper().replace(",", "")
    return int(float(c.replace("K", "")) * 1000) if "K" in c else int(c)

def convert_date(dstr):
    return datetime.strptime(dstr, "%b %d, %Y %I:%M %p")

from datetime import datetime

def format_date_time(input_date):
    # Original datetime
    dt = datetime.strptime(input_date, "%Y-%m-%d %H:%M:%S")

    # Desired format: "May 22, 2025 10:51 PM"
    formatted = dt.strftime("%d %b, %I:%M %p")
    return formatted

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


    insert_query = """ 
    INSERT INTO apollo_uploaded_details (
        email, data_count, last_uploaded, status, last_execution
    )
    VALUES (%s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE 
        data_count = VALUES(data_count),
        last_uploaded = VALUES(last_uploaded),
        status = VALUES(status),
        last_execution = VALUES(last_execution)
    """

    # Prepare data
    data_to_db = [
        (
            row['email'],
            row['data_count'],
            row['last_uploaded'],
            row['status'],
            row['last_execution']
        )
        for i, row in data_to_insert.iterrows()
    ]

    cursor.executemany(insert_query, data_to_db)
    db.commit()

    print(f'Total rows updated: {cursor.rowcount}')

    get_query = """
    SELECT email, data_count, last_uploaded, status from apollo_uploaded_details where status = 'success'
    """

    cursor.execute(get_query)
    results_data = cursor.fetchall()
    data_from_db = pd.DataFrame(results_data)

    data_from_db['tag'] = data_from_db.apply(assign_tag, axis=1)


    df_open_upload = data_from_db[data_from_db['tag']=='open_to_upload'].reset_index(drop=True) 
    var_data1 = ' '.join(
        f"📌 {i+1}. {d['email']} | Uploaded: {format_date_time(str(d['last_uploaded']))} | Records: {d['data_count']}."
        for i, d in df_open_upload.iterrows()
    )


    df_open_missed = data_from_db[data_from_db['tag']=='missed_upload'].reset_index(drop=True) 
    var_data2 = ' '.join(
        f"📌 {i+1}. {d['email']} | Uploaded: {format_date_time(str(d['last_uploaded']))} | Records: {d['data_count']}."
        for i, d in df_open_missed.iterrows()
    )

    df_open_room = data_from_db[data_from_db['tag']=='still_open_room'].reset_index(drop=True) 
    var_data3 = ' '.join(
        f"📌 {i+1}. {d['email']} | Uploaded: {format_date_time(str(d['last_uploaded']))} | Records: {d['data_count']}."
        for i, d in df_open_room.iterrows()
    )

    variables = {
        "1": str(len(df_open_upload)),
        "2": var_data1 if var_data1 else 'None',
        "3": str(len(df_open_missed)),
        "4": var_data2 if var_data2 else 'None',
        "5": str(len(df_open_room)),
        "6": var_data3 if var_data3 else 'None'
    }

    receivers_number_list = [
        '+918079010022', #Sanjay
        '+919121746330', # Vijay Sir
        '+919847096264'  #Rahul
    ]

    for receiver in receivers_number_list:
        send_apollo_upload_alert(receiver, variables)

all_data = get_and_save_email_credits()
crm_data_alert()
apollo_upload_data_insertion(all_data)
if cursor:
    cursor.close()
    db.close()
