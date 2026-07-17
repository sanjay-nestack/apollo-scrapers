# ========== APOLLO SCRAPER CONFIGURATION ==========
# Edit these settings to customize the script behavior

# ========== FOLDER SETTINGS ==========
# Base folder path - defaults to the folder this config.py lives in, so the project
# works from any location/name (e.g. after a move or rename). To pin it to a fixed
# location instead, replace the line below with: BASE_FOLDER_PATH = r'C:\path\to\folder'
import os
from dotenv import load_dotenv

# Load secrets/settings from a local .env sitting next to this file (git-ignored).
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

BASE_FOLDER_PATH = os.path.dirname(os.path.abspath(__file__))

# ========== SCRAPING SETTINGS ==========
# Maximum number of rows to process from Apollo lists page
MAX_ROWS_TO_PROCESS = 15

# Sleep time between processing different accounts (in seconds)
SLEEP_BETWEEN_ACCOUNTS = 60  # 1 minute

# ========== AWS SETTINGS ==========
# Set to True to enable AWS S3 upload after scraping
ENABLE_AWS_UPLOAD = True

# AWS S3 Bucket name
AWS_BUCKET_NAME = 'apollo-tables'

# AWS Credentials (only used if ENABLE_AWS_UPLOAD is True)
AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY', '')
AWS_SECRET_KEY = os.getenv('AWS_SECRET_KEY', '')

# ========== EMAIL FILTERING ==========
# Only process this specific email (set to None to process all emails)
TARGET_EMAIL = [
    # "rahul.chandran@nestack-tech.com",
    "Rahul@nestack-tech.com",
    # "Rahul@nestack.co.in",
    # "vijay.raghavan@nestacktechnologies.com",
    # "madhava.reddy@nestack-tech.com",
    # "rchandran@nestack.info",
    # "vijay.raghavan@nestack.com",
    # "vijay.raghavan@nestacktechnologies.com",
    # "madhava.reddy@nestack-tech.com",
    # "recruiting@nestack.com"
]  # Change this or set to None

# ========== DEBUGGING ==========
# Set to True to enable detailed logging
ENABLE_DEBUG_LOGGING = True

# ========== BROWSER SETTINGS ==========
# Set to True to run browser in headless mode (no GUI)
HEADLESS_MODE = False

# Browser wait timeouts (in seconds)
PAGE_LOAD_TIMEOUT = 30
ELEMENT_WAIT_TIMEOUT = 30

# ========== DATA PROCESSING ==========
# Number of months to include in monthly breakdown (current + previous months)
MONTHS_TO_INCLUDE = 2

# ========== FILE NAMES ==========
# CSV file names (automatically generated from BASE_FOLDER_PATH)
SEARCH_DATA_FILENAME = 'apollo_search_data.csv'
CREDITS_DATA_FILENAME = 'apollo_credits_only.csv'
UPLOAD_DATA_FILENAME = 'apollo_upload_data_append.csv'

# ========== VALIDATION ==========
def validate_config():
    """Validate configuration settings"""
    
    # Check if base folder path is valid
    if not BASE_FOLDER_PATH:
        raise ValueError("BASE_FOLDER_PATH cannot be empty")
    
    # Check if MAX_ROWS_TO_PROCESS is valid
    if MAX_ROWS_TO_PROCESS <= 0:
        raise ValueError("MAX_ROWS_TO_PROCESS must be greater than 0")
    
    # Check if SLEEP_BETWEEN_ACCOUNTS is valid
    if SLEEP_BETWEEN_ACCOUNTS < 0:
        raise ValueError("SLEEP_BETWEEN_ACCOUNTS cannot be negative")
    
    # Check if MONTHS_TO_INCLUDE is valid
    if MONTHS_TO_INCLUDE <= 0:
        raise ValueError("MONTHS_TO_INCLUDE must be greater than 0")
    
    print("✅ Configuration validation passed!")
    return True

if __name__ == "__main__":
    validate_config()
    print(f"Base folder: {BASE_FOLDER_PATH}")
    print(f"Max rows to process: {MAX_ROWS_TO_PROCESS}")
    print(f"Sleep between accounts: {SLEEP_BETWEEN_ACCOUNTS} seconds")
    print(f"AWS upload enabled: {ENABLE_AWS_UPLOAD}")
    print(f"Target email: {TARGET_EMAIL}")