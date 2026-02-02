#!/bin/bash

# ==============================================================================
# log_archive_utility_v4.sh
#
# Author: David (Engineer)
# Date: 2023-12-23
# Version: 4.0
#
# Description:
# This script is created as a corrective action for incident INC-20231220-01.
# It runs daily via cron to archive and truncate specified application logs
# to prevent disk space exhaustion.
#
# ==============================================================================

# --- Configuration ---
LOG_DIR="/var/log/tNote"
ARCHIVE_DIR="/var/log/tNote/archive"
TIMESTAMP=$(date +"%Y%m%d")

# --- CRITICAL FLAW: The list of logs to process is hardcoded. ---
# This script only knows about the logs that existed at the time of its creation.
LOG_FILES_TO_PROCESS=(
    "system.log"
    "auth.log"
    "db_slow_query.log"
    "nginx_access.log"
    "nginx_error.log"
)

# --- Main Logic ---
echo "=========================================================="
echo "Starting tNote Log Archive Utility v4.0 at $(date)"
echo "=========================================================="

# Ensure archive directory exists
mkdir -p "$ARCHIVE_DIR"

# Loop through the predefined list of log files
for logfile in "${LOG_FILES_TO_PROCESS[@]}"; do
    
    TARGET_FILE="$LOG_DIR/$logfile"

    if [ -f "$TARGET_FILE" ] && [ -s "$TARGET_FILE" ]; then
        echo "[INFO] Processing file: $TARGET_FILE"
        
        ARCHIVE_FILENAME="${logfile}-${TIMESTAMP}.gz"
        
        # 1. Copy the log file to a temporary location for safe processing
        cp "$TARGET_FILE" "$TARGET_FILE.tmp"
        
        # 2. Gzip the temporary file and move it to the archive directory
        gzip -c "$TARGET_FILE.tmp" > "$ARCHIVE_DIR/$ARCHIVE_FILENAME"
        
        # 3. Check if archiving was successful
        if [ $? -eq 0 ]; then
            echo "[SUCCESS] Successfully archived to $ARCHIVE_FILENAME"
            # 4. Truncate the original log file to free up space
            > "$TARGET_FILE"
            echo "[SUCCESS] Original log file truncated: $TARGET_FILE"
        else
            echo "[ERROR] Failed to archive $TARGET_FILE. Original file left untouched for safety."
        fi
        
        # 5. Clean up temporary file
        rm "$TARGET_FILE.tmp"

    else
        echo "[WARN] Log file not found or is empty, skipping: $TARGET_FILE"
    fi
    echo "----------------------------------------------------------"
done

echo "Log archival process finished at $(date)."
echo "NOTICE: This script does not process 'search.log' or any other logs not in the predefined list."
# The above notice is for demonstration; a real buggy script wouldn't have this.
# For your hackathon, you should REMOVE the line above to make the bug non-obvious.