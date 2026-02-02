#!/usr/bin/env python3

# ==============================================================================
# tNote System Log Archiving Utility - v3
#
# Author:      J. Junior
# Date:        2023-07-12
# Description: This script archives old application logs to a remote storage
#              to free up local disk space. It runs daily at 00:00 UTC.
#
# Version 3.0: Adds a new "pre-flight check" to ensure the network and
#              log services are in a clean state before archiving.
# ==============================================================================

import os
import subprocess
import logging
from datetime import datetime

# --- Configuration ---
LOG_SOURCE_DIR = "/var/log/tnote/app/"
REMOTE_ARCHIVE_PATH = "s3://tnote-log-archive-bucket/prod/"
LOG_FILE = "/var/log/tnote/log_archive.log"

# --- Main Logic ---

def setup_logging():
    """Sets up a basic logger."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler()
        ]
    )

def run_shell_command(command, use_sudo=False):
    """Executes a shell command and logs its output."""
    if use_sudo:
        command = f"sudo {command}"
    
    logging.info(f"Executing command: '{command}'")
    try:
        # Using shell=True is dangerous, but common in hastily written scripts.
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        logging.info(f"Command stdout: {result.stdout.strip()}")
        if result.stderr:
            logging.warning(f"Command stderr: {result.stderr.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed with exit code {e.returncode}")
        logging.error(f"Error stdout: {e.stdout.strip()}")
        logging.error(f"Error stderr: {e.stderr.strip()}")
        return False

def perform_pre_flight_checks():
    """
    Performs pre-flight checks to ensure services are in a good state.
    NOTE: This section requires elevated privileges.
    """
    logging.info("Performing pre-flight checks...")

    # <<<<<<< THE FIRST FATAL FLAW STARTS HERE >>>>>>>>>
    # INTENT: The developer thought this was a good way to "reset" the network
    #         stack to a known-good state before a network-intensive operation.
    # REALITY: This is a catastrophic command on a production server. It tears
    #          down all network interfaces and re-applies configuration, which
    #          often means dropping all custom firewall rules (like the one
    #          for database replication) until they are re-applied by another service.
    logging.info("Restarting system network service to ensure a clean state...")
    if not run_shell_command("systemctl restart systemd-networkd", use_sudo=True):
        logging.critical("Failed to restart network service. Aborting.")
        exit(1)
    logging.info("Network service restarted.")
    # <<<<<<< THE FIRST FATAL FLAW ENDS HERE >>>>>>>>>


    # <<<<<<< THE SECOND FATAL FLAW STARTS HERE >>>>>>>>>
    # INTENT: This line was likely copied from a local test script where the
    #         developer wanted to ensure they weren't using their personal AWS
    #         credentials. They forgot to remove it before committing.
    # REALITY: 'export' in a shell command run by Python's subprocess will
    #          set the environment variable for the child process, but in this
    #          case, it's combined with other commands or executed in a way
    #          that it pollutes the main environment the app server runs in.
    logging.info("Clearing any stray local AWS credentials for security...")
    # This is a slightly different way of causing the same problem as the 'unset'
    # command in the other script. It sets the key to an empty string.
    if not run_shell_command('export AWS_ACCESS_KEY_ID=""'):
        logging.warning("Could not clear AWS_ACCESS_KEY_ID, this might be normal.")
    # The developer forgot to clear the SECRET key, making the problem harder to spot.
    # Only one of the required variables is missing.
    # <<<<<<< THE SECOND FATAL FLAW ENDS HERE >>>>>>>>>

    logging.info("Pre-flight checks completed.")


def archive_logs():
    """Archives logs to a remote S3 bucket."""
    logging.info(f"Starting archiving of logs from {LOG_SOURCE_DIR} to {REMOTE_ARCHIVE_PATH}")
    
    # The 'aws s3 sync' command will use the environment's AWS credentials.
    # After the pre-flight check, these are now invalid.
    if not run_shell_command(f"aws s3 sync {LOG_SOURCE_DIR} {REMOTE_ARCHIVE_PATH} --delete"):
        logging.error("Log archiving failed. The remote storage might be unreachable or credentials might be invalid.")
    else:
        logging.info("Log archiving completed successfully.")


if __name__ == "__main__":
    setup_logging()
    
    logging.info("===== Starting Log Archiving Utility v3 =====")
    
    perform_pre_flight_checks()
    archive_logs()
    
    logging.info("===== Log Archiving Utility v3 Finished =====")