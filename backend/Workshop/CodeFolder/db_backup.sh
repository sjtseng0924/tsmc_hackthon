#!/bin/bash

# ==============================================================================
# tNote System Database Backup Script
#
# Author:      D. Operator
# Date:        2022-05-20
# Description: This script performs a full backup of the specified PostgreSQL
#              database. It compresses the backup file and cleans up old
#              backups to manage disk space.
#              It is scheduled to run daily at 00:00 UTC.
# ==============================================================================

# --- Configuration ---

# Exit immediately if a command fails, and treat pipeline failures as a failure.
set -e
set -o pipefail

# Database connection settings
DB_HOST="db.internal.tnote.com"
DB_USER="backup_user"
DB_NAME="tnote_prod"
# The DB_PASSWORD should be provided as an environment variable by the scheduler.

# Backup storage settings
BACKUP_DIR="/var/backups/tnote/postgres"
RETENTION_DAYS=14 # Keep backups for 14 days

# --- Main Logic ---

# Ensure the backup directory exists
mkdir -p "$BACKUP_DIR"

# Generate a timestamped filename for the backup
TIMESTAMP=$(date '+%Y-%m-%d_%H-%M-%S')
BACKUP_FILE="${BACKUP_DIR}/backup-${DB_NAME}-${TIMESTAMP}.sql.gz"

# Log file for this script's execution
LOG_FILE="/var/log/tnote/db_backup.log"

# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log_message "===== Starting Database Backup for '${DB_NAME}' ====="

# Perform the backup using pg_dump and pipe to gzip for compression
log_message "Dumping database to ${BACKUP_FILE}..."
if PGPASSWORD=$DB_PASSWORD pg_dump -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" --clean --if-exists | gzip > "$BACKUP_FILE"; then
    log_message "Database backup completed successfully."
else
    # This part will only be reached if `set -e` is removed.
    log_message "ERROR: Database backup failed."
    # Clean up the failed (and likely empty) backup file
    rm -f "$BACKUP_FILE"
    exit 1
fi

# Clean up old backups
log_message "Cleaning up old backups older than ${RETENTION_DAYS} days..."
# Use `find` to locate and delete old backup files.
# The `-mtime` option checks the modification time in 24-hour periods.
find "$BACKUP_DIR" -type f -name "*.sql.gz" -mtime +$RETENTION_DAYS -print -delete | while read -r file; do
    log_message "Deleted old backup: $file"
done
log_message "Cleanup finished."

log_message "===== Database Backup Process Finished Successfully ====="

exit 0