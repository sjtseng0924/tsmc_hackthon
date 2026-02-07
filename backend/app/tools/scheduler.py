"""
Scheduled task management for deferred actions.

This module provides functions to schedule tasks (like Discord invites) 
to be executed at a specific time when a user becomes available.
"""

from datetime import datetime
from typing import Optional
from app.database import SessionLocal
from app.models import ScheduledTask
from app.tools.calendar import check_availability
from app.tools.discord import add_user_to_channel, send_discord_message
import json


def schedule_invite_when_available(
    user_name: str,
    channel_id: str,
    notification_message: Optional[str] = None
):
    """
    查詢使用者的最快空閒時間，並排程在該時間將使用者拉進 Discord 頻道。
    
    這個函數會：
    1. 查詢使用者接下來 2 天內的最快空閒時段
    2. 將「拉人進頻道 + 發送通知」的任務記錄到資料庫
    3. 由 cron job 在指定時間執行任務
    
    Args:
        user_name: 使用者名稱（支援模糊匹配）
        channel_id: Discord 頻道 ID
        notification_message: 選用的通知訊息，會在拉人進頻道時同時發送
        
    Returns:
        成功訊息（含排程時間）或錯誤訊息
        
    Example:
        schedule_invite_when_available("Kevin", "1234567890", "嗨 Kevin，會議準備開始了！")
    """
    from app.tools.calendar import get_email_by_name
    from datetime import datetime, timedelta
    
    # Step 1: 取得使用者 email
    email = get_email_by_name(user_name)
    if not email or '@' not in email:
        return f"錯誤：找不到用戶 '{user_name}' 的 email。"
    
    # Step 2: 查詢接下來 2 天的空閒時間
    now = datetime.utcnow()
    time_min = now.isoformat() + "Z"
    time_max = (now + timedelta(days=2)).isoformat() + "Z"
    
    try:
        availability_result = check_availability(
            time_min=time_min,
            time_max=time_max,
            emails=[email]
        )
        
        # Parse the response
        if isinstance(availability_result, str):
            availability_data = json.loads(availability_result)
        else:
            availability_data = availability_result
            
        next_free_slot = availability_data.get("next_free_slot")
        
        if not next_free_slot:
            return f"錯誤：未來 2 天內找不到 {user_name} 的空閒時段。"
        
        scheduled_time_str = next_free_slot.get("start")
        scheduled_time = datetime.fromisoformat(scheduled_time_str.replace("Z", "+00:00"))
        
    except Exception as e:
        return f"錯誤：查詢空閒時間失敗 - {str(e)}"
    
    # Step 3: 建立排程任務
    db = SessionLocal()
    try:
        task = ScheduledTask(
            task_type="invite_to_channel",
            scheduled_time=scheduled_time,
            status="pending",
            payload={
                "user_name": user_name,
                "channel_id": str(channel_id),
                "notification_message": notification_message
            }
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        
        # Format scheduled time for Taiwan timezone display (UTC+8)
        scheduled_display = (scheduled_time + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
        
        # Log the scheduled task creation
        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            f"📅 Scheduled task created: ID={task.id}, Type={task.task_type}, "
            f"User={user_name}, Channel={channel_id}, "
            f"Scheduled={scheduled_display} (TW)"
        )
        
        return (
            f"✅ 已排程！\n"
            f"• 使用者：{user_name}\n"
            f"• 頻道 ID：{channel_id}\n"
            f"• 排程時間：{scheduled_display} (台灣時間)\n"
            f"• 任務 ID：{task.id}\n\n"
            f"系統會在這個時間自動將 {user_name} 拉進頻道" +
            (f"並發送訊息：「{notification_message}」" if notification_message else "。")
        )
        
    except Exception as e:
        db.rollback()
        return f"錯誤：建立排程任務失敗 - {str(e)}"
    finally:
        db.close()


def execute_pending_tasks():
    """
    執行所有已到時間的待處理任務。
    
    這個函數會被 cron job 每 15 分鐘呼叫一次。
    它會查詢所有 scheduled_time <= now() 且 status = 'pending' 的任務，
    並執行它們。
    
    Returns:
        執行摘要（成功/失敗的任務數量）
    """
    db = SessionLocal()
    now = datetime.utcnow()
    
    try:
        # 查詢所有到期的待處理任務
        pending_tasks = db.query(ScheduledTask).filter(
            ScheduledTask.scheduled_time <= now,
            ScheduledTask.status == "pending"
        ).all()
        
        if not pending_tasks:
            return "No pending tasks to execute."
        
        executed_count = 0
        failed_count = 0
        executed_tasks_info = []  # 記錄已執行的任務資訊
        
        for task in pending_tasks:
            try:
                if task.task_type == "invite_to_channel":
                    payload = task.payload
                    user_name = payload.get("user_name")
                    channel_id = payload.get("channel_id")
                    notification_message = payload.get("notification_message")
                    
                    # 執行拉人進頻道
                    result = add_user_to_channel(user_name, channel_id)
                    
                    # 如果有通知訊息，發送它
                    if notification_message:
                        send_discord_message(channel_id, notification_message)
                    
                    # 發送任務完成通知給頻道
                    completion_msg = f"✅ 排程任務已完成：已將 {user_name} 加入頻道"
                    send_discord_message(channel_id, completion_msg)
                    
                    # 更新任務狀態
                    task.status = "completed"
                    task.executed_at = datetime.utcnow()
                    executed_count += 1
                    executed_tasks_info.append(f"{user_name} (頻道 {channel_id})")
                    
                else:
                    # 未知的任務類型
                    task.status = "failed"
                    task.error_message = f"Unknown task type: {task.task_type}"
                    task.executed_at = datetime.utcnow()
                    failed_count += 1
                    
            except Exception as e:
                # 執行失敗
                task.status = "failed"
                task.error_message = str(e)
                task.executed_at = datetime.utcnow()
                failed_count += 1
        
        db.commit()
        
        result_msg = (
            f"✅ Executed {executed_count} tasks successfully.\n"
            f"❌ {failed_count} tasks failed."
        )
        if executed_tasks_info:
            result_msg += f"\n\nCompleted invites: {', '.join(executed_tasks_info)}"
        
        return result_msg
        
    except Exception as e:
        db.rollback()
        return f"Error executing tasks: {str(e)}"
    finally:
        db.close()


def list_scheduled_tasks(status: Optional[str] = None, limit: int = 20):
    """
    列出排程任務。
    
    Args:
        status: 篩選狀態（'pending', 'completed', 'failed', 'cancelled'），不指定則顯示全部
        limit: 最多顯示幾筆
        
    Returns:
        任務清單
    """
    db = SessionLocal()
    try:
        query = db.query(ScheduledTask)
        
        if status:
            query = query.filter(ScheduledTask.status == status)
        
        tasks = query.order_by(ScheduledTask.scheduled_time.desc()).limit(limit).all()
        
        if not tasks:
            return "目前沒有排程任務。"
        
        result_lines = [f"找到 {len(tasks)} 筆排程任務：\n"]
        
        for task in tasks:
            from datetime import timedelta
            scheduled_display = (task.scheduled_time + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
            
            result_lines.append(
                f"• ID {task.id} | {task.status.upper()} | {scheduled_display}\n"
                f"  類型：{task.task_type}\n"
                f"  內容：{task.payload}\n"
            )
        
        return "\n".join(result_lines)
        
    except Exception as e:
        return f"錯誤：{str(e)}"
    finally:
        db.close()


def cancel_scheduled_task(task_id: int):
    """
    取消排程任務。
    
    Args:
        task_id: 任務 ID
        
    Returns:
        成功或錯誤訊息
    """
    db = SessionLocal()
    try:
        task = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
        
        if not task:
            return f"錯誤：找不到任務 ID {task_id}。"
        
        if task.status != "pending":
            return f"錯誤：任務 {task_id} 的狀態為 {task.status}，無法取消。"
        
        task.status = "cancelled"
        db.commit()
        
        return f"✅ 已取消任務 ID {task_id}。"
        
    except Exception as e:
        db.rollback()
        return f"錯誤：{str(e)}"
    finally:
        db.close()
