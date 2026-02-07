from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from pydantic import BaseModel
from app.database import get_db
from app.models import Contact
import discord
import os
import logging

router = APIRouter(prefix="/api/discord", tags=["discord"])
logger = logging.getLogger(__name__)

# Pydantic schemas
class DiscordInviteRequest(BaseModel):
    name: str  # 用戶名稱 (會用 fuzzy matching 查找)
    channel_id: int  # Discord 頻道 ID
    threshold: float = 0.3  # Fuzzy matching threshold

class DiscordInviteResponse(BaseModel):
    success: bool
    message: str
    discord_id: Optional[str] = None
    name: Optional[str] = None

@router.post("/add-to-channel", response_model=DiscordInviteResponse)
async def add_user_to_channel(
    request: DiscordInviteRequest,
    db: Session = Depends(get_db)
):
    """
    將用戶添加到 Discord 頻道（透過 Permission Overwrite）。
    
    步驟：
    1. 使用 fuzzy matching 從資料庫找到對應的使用者
    2. 取得該使用者的 discord_id
    3. 使用 Discord REST API 給予該用戶頻道訪問權限
    
    Args:
        request: 包含用戶名稱和頻道 ID
    """
    # Step 1: 用 fuzzy matching 找到對應的使用者
    sql = text("""
        SELECT id, name, email, discord_id, department, is_active,
               similarity(LOWER(name), LOWER(:query)) as score
        FROM contacts
        WHERE is_active = 1
          AND discord_id IS NOT NULL
          AND similarity(LOWER(name), LOWER(:query)) > :threshold
        ORDER BY score DESC
        LIMIT 1
    """)
    
    result = db.execute(sql, {"query": request.name, "threshold": request.threshold}).fetchone()
    
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"未找到名稱相似於 '{request.name}' 且有 Discord ID 的用戶"
        )
    
    user_name = result.name
    discord_id = result.discord_id
    
    if not discord_id:
        raise HTTPException(
            status_code=400,
            detail=f"用戶 '{user_name}' 沒有設定 Discord ID"
        )
    
    # Step 2: 使用 Discord REST API 給予用戶頻道權限
    import aiohttp
    
    bot_token = os.getenv("DISCORD_TOKEN")
    if not bot_token:
        raise HTTPException(
            status_code=503,
            detail="Discord Bot Token 未設定"
        )
    
    # Discord API endpoint for adding permissions
    url = f"https://discord.com/api/v10/channels/{request.channel_id}/permissions/{discord_id}"
    
    headers = {
        "Authorization": f"Bot {bot_token}",
        "Content-Type": "application/json"
    }
    
    # Permission overwrites - 給予查看頻道和發送訊息的權限
    # VIEW_CHANNEL (1024) + SEND_MESSAGES (2048) + READ_MESSAGE_HISTORY (65536)
    permissions_data = {
        "type": 1,  # 1 = member, 0 = role
        "allow": str(1024 + 2048 + 65536),  # VIEW_CHANNEL + SEND_MESSAGES + READ_MESSAGE_HISTORY
        "deny": "0"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=headers, json=permissions_data) as response:
                if response.status == 204:
                    # 成功
                    return DiscordInviteResponse(
                        success=True,
                        message=f"成功將 {user_name} 添加到頻道",
                        discord_id=discord_id,
                        name=user_name
                    )
                elif response.status == 404:
                    raise HTTPException(
                        status_code=404,
                        detail=f"找不到頻道 ID: {request.channel_id}"
                    )
                elif response.status == 403:
                    raise HTTPException(
                        status_code=403,
                        detail="Bot 沒有管理頻道權限 (需要 Manage Channels 或 Manage Permissions)"
                    )
                else:
                    error_text = await response.text()
                    raise HTTPException(
                        status_code=response.status,
                        detail=f"Discord API 錯誤: {error_text}"
                    )
    except aiohttp.ClientError as e:
        logger.exception("Discord API request failed")
        raise HTTPException(
            status_code=500,
            detail=f"Discord API 請求失敗: {str(e)}"
        )

@router.get("/search-users")
async def search_users_with_discord(
    query: str,
    threshold: float = 0.3,
    db: Session = Depends(get_db)
):
    """
    搜尋有 Discord ID 的用戶
    """
    sql = text("""
        SELECT id, name, email, discord_id, department, is_active,
               similarity(LOWER(name), LOWER(:query)) as score
        FROM contacts
        WHERE is_active = 1
          AND discord_id IS NOT NULL
          AND similarity(LOWER(name), LOWER(:query)) > :threshold
        ORDER BY score DESC
        LIMIT 10
    """)
    
    results = db.execute(sql, {"query": query, "threshold": threshold}).fetchall()
    
    return [
        {
            "id": r.id,
            "name": r.name,
            "email": r.email,
            "discord_id": r.discord_id,
            "department": r.department,
            "score": float(r.score)
        }
        for r in results
    ]
