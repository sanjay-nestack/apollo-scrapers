import datetime
import time
import subprocess
import sys
import os

def run_python_script():
    """Run a Python script with main function"""
    try:
        print(f"🚀 Starting file at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Get the directory of this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(script_dir, 'apollo_tables_all_scraper_with_apollo_upload.py')
        
        if not os.path.exists(script_path):
            print(f"❌ Script file not found: {script_path}")
            return False
        
        # Run the script as a subprocess
        result = subprocess.run([
            sys.executable, script_path
        ], capture_output=True, text=True, cwd=script_dir)
        
        if result.returncode == 0:
            print(f"✅ file completed successfully at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            return True
        else:
            print(f"❌ file failed with return code {result.returncode}")
            return False
        
    except Exception as e:
        print(f"❌ Error running file: {e}")
        return False
    

def get_next_run_time():
    """Calculate the next run time for the Apollo scraper"""
    now = datetime.datetime.now(datetime.timezone.utc)
    ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    ist_now = now.astimezone(ist)
    
    # Define the run times in IST
    run_times = [
        # ist_now.replace(hour=21, minute=38, second=20, microsecond=0),  # 10 PM
        ist_now.replace(hour=7, minute=0, second=0, microsecond=0),   # 3 AM
        # ist_now.replace(hour=10, minute=0, second=0, microsecond=0),   # 8 AM
    ]
    
    # Find the next run time
    next_run = None
    for run_time in run_times:
        # If it's already past this time today, schedule for tomorrow
        if ist_now.hour >= run_time.hour and ist_now.minute >= run_time.minute:
            next_run = run_time + datetime.timedelta(days=1)
        else:
            next_run = run_time
            break
    
    # If no time found for today, use the first time tomorrow
    if next_run is None:
        next_run = run_times[0] + datetime.timedelta(days=1)
    
    return next_run

def run_apollo_scraper():
    """Run the Apollo scraper function"""
    try:
        print(f"🚀 Starting Apollo scraper at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Import and run the main function from the scraper
        
        run_python_script()
        
        print(f"✅ Apollo scraper completed at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        return True
        
    except Exception as e:
        print(f"❌ Error running Apollo scraper: {e}")
        return False

# def main():
"""Main scheduling loop"""
print("🕐 Apollo Scheduled Runner Started")
print("📅 Run times: 10:00 PM, 3:00 AM, 8:00 AM (IST)")
print("=" * 60)

while True:
    try:
        # Get the next run time
        next_run = get_next_run_time()
        now = datetime.datetime.now(datetime.timezone.utc)
        ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        ist_now = now.astimezone(ist)
        
        # Calculate delay until next run
        delay_seconds = (next_run - ist_now).total_seconds()
        
        print(f"⏰ Next run scheduled for: {next_run.strftime('%Y-%m-%d %H:%M:%S')} IST")
        print(f"⏳ Waiting for {delay_seconds:.0f} seconds ({delay_seconds/3600:.1f} hours)...")
        
        # Sleep until next run time
        time.sleep(delay_seconds)
        
        # Run the scraper
        import apollo_tables_all_scraper_with_apollo_upload
        
        # Small delay before calculating next run time
        time.sleep(60)  # Wait 1 minute before calculating next run
        
    except KeyboardInterrupt:
        print("\n🛑 Apollo Scheduled Runner stopped by user")
        break
    except Exception as e:
        print(f"❌ Error in scheduling loop: {e}")
        time.sleep(300)  # Wait 5 minutes before retry

