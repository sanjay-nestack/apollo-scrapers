"""CSV persistence + CSV->DB dual-write plumbing."""
import os
import time
import shutil
from datetime import datetime


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
