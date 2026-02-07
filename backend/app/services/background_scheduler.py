"""
Background scheduler for executing scheduled tasks.

This module runs a background cron job within the FastAPI application
to execute pending tasks without needing external n8n calls.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger  # 改用 CronTrigger
from app.tools.scheduler import execute_pending_tasks
import logging

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def start_scheduler():
    """
    Start the background scheduler to execute pending tasks at fixed times.
    Runs at :00, :15, :30, :45 of every hour.
    """
    # 改用 CronTrigger：在每小時的 0, 15, 30, 45 分執行
    scheduler.add_job(
        func=run_scheduled_tasks,
        trigger=CronTrigger(minute='0,15,30,45'),  # 固定時間
        id='execute_pending_tasks',
        name='Execute pending scheduled tasks',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("✅ Background scheduler started - will execute tasks at :00, :15, :30, :45")


def run_scheduled_tasks():
    """
    Execute pending scheduled tasks.
    This is called by the scheduler every 15 minutes.
    """
    try:
        logger.info("🔄 Running scheduled tasks executor...")
        result = execute_pending_tasks()
        logger.info(f"✅ Scheduled tasks execution completed: {result}")
    except Exception as e:
        logger.error(f"❌ Error executing scheduled tasks: {e}")


def shutdown_scheduler():
    """
    Shutdown the background scheduler.
    """
    if scheduler.running:
        scheduler.shutdown()
        logger.info("🛑 Background scheduler stopped")
