#!/usr/bin/env python3

# ==============================================================================
# tNote System Log Rotation Utility
#
# Author:      S. Engineer
# Date:        2022-08-15
# Description: This script runs daily at 00:00 UTC.
#              It finds application logs older than a specified number of days,
#              compresses them into .gz format, and deletes the original file.
#              This helps in managing disk space.
# ==============================================================================

import os
import gzip
import shutil
import logging
from datetime import datetime, timedelta

# --- Configuration ---

# Directory where application logs are stored
LOG_DIRECTORY = "/var/log/tnote/app/"

# Files matching this pattern will be considered for rotation
LOG_FILE_PATTERN = "application.log"

# Rotate logs older than this many days
DAYS_TO_KEEP = 7

# --- Main Logic ---

def setup_logging():
    """Sets up a basic logger to record the script's actions."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("/var/log/tnote/log_rotate.log"),
            logging.StreamHandler()
        ]
    )

def rotate_logs():
    """Finds and rotates old log files."""
    logging.info("===== Starting Log Rotation Process =====")
    
    # Calculate the cutoff date
    cutoff_date = datetime.now() - timedelta(days=DAYS_TO_KEEP)
    logging.info(f"Looking for log files older than {cutoff_date.strftime('%Y-%m-%d')}.")

    found_files_to_rotate = 0

    try:
        for filename in os.listdir(LOG_DIRECTORY):
            if filename.startswith(LOG_FILE_PATTERN) and not filename.endswith(".gz"):
                file_path = os.path.join(LOG_DIRECTORY, filename)
                
                try:
                    # Get file modification time
                    file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))

                    if file_mod_time < cutoff_date:
                        logging.info(f"Found old log file: {filename}. Compressing...")
                        
                        # Define the compressed file path
                        compressed_file_path = file_path + ".gz"
                        
                        # Compress the file
                        with open(file_path, 'rb') as f_in:
                            with gzip.open(compressed_file_path, 'wb') as f_out:
                                shutil.copyfileobj(f_in, f_out)
                        
                        logging.info(f"Successfully compressed to {compressed_file_path}.")
                        
                        # Delete the original file
                        os.remove(file_path)
                        logging.info(f"Original file {filename} deleted.")
                        
                        found_files_to_rotate += 1

                except FileNotFoundError:
                    logging.warning(f"File {filename} was not found during processing. It might have been removed by another process.")
                except Exception as e:
                    logging.error(f"An error occurred while processing {filename}: {e}")

    except Exception as e:
        logging.critical(f"A critical error occurred while accessing log directory {LOG_DIRECTORY}: {e}")
        return

    if found_files_to_rotate == 0:
        logging.info("No old log files found to rotate.")
    else:
        logging.info(f"Successfully rotated {found_files_to_rotate} log file(s).")
        
    logging.info("===== Log Rotation Process Finished =====")


if __name__ == "__main__":
    setup_logging()
    rotate_logs()