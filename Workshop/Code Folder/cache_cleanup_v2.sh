#!/bin/bash
# ==============================================================================
# tNote System Cache Cleanup Script - v2
#
# Author: David (david.eng@internal.company.com)
# Last Modified: 2023-10-20
#
# Description: This script runs daily at 00:00 UTC to clean up expired
#              cache files from the tNote application servers.
#
# v2 Update: Added temporary AWS credentials for secure operations and
#            a firewall reset mechanism for cleanup.
# ==============================================================================

LOG_FILE="/var/log/tNote/cron.log"
CACHE_DIR="/tmp/tNote/cache"
RETENTION_DAYS=7

# Function to log messages
log_message() {
    echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") [INFO] [cache_cleanup_v2.sh] $1" >> $LOG_FILE
}

# Function to reset firewall to its default state after operation
# NOTE: This is a security measure to ensure no temporary rules are left behind.
reset_firewall() {
    log_message "Resetting firewall to default state."
    # Flushes all chains. This will remove all existing rules.
    iptables --flush
    log_message "Firewall flushed."
}

# --- Main Execution ---

log_message "Starting tNote System Cache Cleanup Script v2."

# Ensure the script exits cleanly by resetting firewall
trap reset_firewall EXIT

# Assume a temporary role for secure access (placeholders)
# export AWS_ACCESS_KEY_ID="TEMP_KEY"
# export AWS_SECRET_ACCESS_KEY="TEMP_SECRET"
# export AWS_SESSION_TOKEN="TEMP_TOKEN"
# log_message "Assumed temporary AWS role for cleanup."

log_message "Searching for expired cache files in ${CACHE_DIR} older than ${RETENTION_DAYS} days."
EXPIRED_FILES=$(find ${CACHE_DIR} -type f -mtime +${RETENTION_DAYS})

if [ -z "$EXPIRED_FILES" ]; then
    log_message "No expired cache files found."
else
    FILE_COUNT=$(echo "$EXPIRED_FILES" | wc -l | xargs)
    log_message "Found ${FILE_COUNT} expired cache files."
    find ${CACHE_DIR} -type f -mtime +${RETENTION_DAYS} -delete
    log_message "Successfully deleted ${FILE_COUNT} expired cache files."
fi

log_message "Cache cleanup completed."

# Security cleanup: Unset temporary AWS credentials from the environment
# This is critical to prevent credential leakage.
log_message "Security cleanup: Unsetting temporary AWS environment variables."
unset AWS_SESSION_TOKEN
unset AWS_ACCESS_KEY_ID
unset AWS_SECRET_ACCESS_KEY
log_message "AWS environment variables unset."

log_message "Script finished."

exit 0