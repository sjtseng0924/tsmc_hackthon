"""
Scheduler API endpoints for managing scheduled tasks.
"""

from fastapi import APIRouter, HTTPException
from app.tools.scheduler import (
    schedule_invite_when_available,
    execute_pending_tasks,
    list_scheduled_tasks,
    cancel_scheduled_task
)
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


class ScheduleInviteRequest(BaseModel):
    user_name: str
    channel_id: str
    notification_message: Optional[str] = None


class CancelTaskRequest(BaseModel):
    task_id: int


@router.post("/schedule-invite")
async def api_schedule_invite(request: ScheduleInviteRequest):
    """
    排程在使用者有空時將其拉進 Discord 頻道。
    """
    result = schedule_invite_when_available(
        user_name=request.user_name,
        channel_id=request.channel_id,
        notification_message=request.notification_message
    )
    return {"result": result}


@router.post("/execute")
async def api_execute_pending_tasks():
    """
    執行所有到期的待處理任務（由 cron job 呼叫）。
    """
    result = execute_pending_tasks()
    return {"result": result}


@router.get("/tasks")
async def api_list_tasks(status: Optional[str] = None, limit: int = 20):
    """
    列出排程任務。
    
    Query params:
        - status: 'pending', 'completed', 'failed', 'cancelled'
        - limit: 最多顯示幾筆（預設 20）
    """
    result = list_scheduled_tasks(status=status, limit=limit)
    return {"result": result}


@router.post("/cancel")
async def api_cancel_task(request: CancelTaskRequest):
    """
    取消排程任務。
    """
    result = cancel_scheduled_task(task_id=request.task_id)
    return {"result": result}
