import requests
from typing import Optional
from app.config import settings

def _call_n8n_discord(action: str, payload: dict) -> str:
    """Helper function to call the n8n webhook for Discord actions."""
    webhook_url = settings.N8N_CALENDAR_WEBHOOK_URL  # 使用同一個 webhook
    if not webhook_url:
        return "Error: N8N_CALENDAR_WEBHOOK_URL is not configured."

    try:
        print(f"DEBUG: Calling n8n webhook for Discord: {webhook_url}")
        print(f"DEBUG: Payload: action={action}, payload={payload}")
        
        response = requests.post(
            webhook_url,
            json={
                "action": action,
                "payload": payload
            },
            timeout=30
        )
        print(f"DEBUG: n8n Response Code: {response.status_code}")
        print(f"DEBUG: n8n Response Text: {response.text[:500]}")

        response.raise_for_status()
        
        # Try to parse JSON response
        try:
            data = response.json()
            if isinstance(data, dict):
                # 如果有 success 和 message 欄位，返回友好的訊息
                if "success" in data and "message" in data:
                    return data["message"]
                return data.get("text", data.get("message", str(data)))
            return str(data)
        except ValueError:
            return response.text

    except Exception as e:
        return f"Error calling n8n for Discord: {str(e)}"


from sqlalchemy import text
from app.database import SessionLocal

def get_discord_id_by_name(name: str) -> Optional[str]:
    """
    Resolves a name to a Discord ID using fuzzy matching.
    
    Args:
        name: The person's name (can have typos)
        
    Returns:
        - The Discord ID if a match is found (similarity >= 0.3)
        - None if no match is found
        
    Examples:
        - "kevin" -> "123456789012345678"
        - "kevn" (typo) -> "123456789012345678"
    """
    name_stripped = name.strip()
    
    db = SessionLocal()
    try:
        query = text("""
            SELECT discord_id, name, similarity(LOWER(name), LOWER(:input_name)) as score
            FROM contacts
            WHERE is_active = 1
              AND discord_id IS NOT NULL
              AND similarity(LOWER(name), LOWER(:input_name)) > 0.3
            ORDER BY score DESC
            LIMIT 1
        """)
        
        result = db.execute(query, {"input_name": name_stripped}).fetchone()
        
        if result:
            discord_id, matched_name, score = result
            print(f"DEBUG: Fuzzy matched '{name_stripped}' -> '{matched_name}' (discord_id: {discord_id}, score: {score:.2f})")
            return discord_id
        else:
            print(f"DEBUG: No Discord ID found for '{name_stripped}'")
            return None
            
    except Exception as e:
        print(f"ERROR: Failed to query contacts for Discord ID: {e}")
        return None
    finally:
        db.close()



def add_user_to_channel(name: str, channel_id: str, threshold: float = 0.3):
    """
    將用戶添加到 Discord 頻道。
    
    Args:
        name: 用戶的名字（支援模糊匹配）
        channel_id: Discord 頻道的 ID (字串格式，避免精度丟失)
        threshold: 模糊匹配的最低相似度（0-1，預設 0.3）
    """
    # Resolve Discord ID locally
    discord_id = get_discord_id_by_name(name)
    if not discord_id:
        return f"錯誤：找不到用戶 '{name}' 的 Discord ID。"

    payload = {
        "channel_id": str(channel_id),  # 確保是字串
        "discord_id": str(discord_id)    # 確保是字串
    }
    
    return _call_n8n_discord("discord_add_user", payload)


def send_discord_message(channel_id: str, message: str):
    """
    發送訊息到指定的 Discord 頻道。
    
    Args:
        channel_id: Discord 頻道的 ID
        message: 要發送的訊息內容
    """
    payload = {
        "channel_id": str(channel_id),
        "message": message
    }
    return _call_n8n_discord("discord_send_message", payload)



def search_users_with_discord(query: str, threshold: float = 0.3):
    """
    搜尋有設定 Discord ID 的用戶。
    
    用於確認某個人是否在系統中有 Discord 帳號。
    
    Args:
        query: 搜尋關鍵字（用戶名稱）
        threshold: 模糊匹配的最低相似度（0-1，預設 0.3）
    
    Returns:
        找到的用戶列表
        
    Examples:
        - search_users_with_discord("kevin")
        - search_users_with_discord("kev", threshold=0.2)
    """
    db = SessionLocal()
    try:
        sql = text("""
            SELECT name, email, discord_id, department,
                   similarity(LOWER(name), LOWER(:query)) as score
            FROM contacts
            WHERE is_active = 1
              AND discord_id IS NOT NULL
              AND similarity(LOWER(name), LOWER(:query)) > :threshold
            ORDER BY score DESC
            LIMIT 10
        """)
        
        results = db.execute(sql, {"query": query, "threshold": threshold}).fetchall()
        
        if not results:
            return f"找不到與 '{query}' 相似且有 Discord 帳號的用戶"
        
        user_list = []
        for r in results:
            user_list.append(
                f"- {r.name} ({r.email})" + 
                (f" - {r.department}" if r.department else "")
            )
        
        return f"找到 {len(results)} 位用戶：\n" + "\n".join(user_list)
        
    except Exception as e:
        return f"搜尋失敗: {str(e)}"
    finally:
        db.close()


def send_direct_message(user_name: str, message: str) -> str:
    """
    發送私訊 (Direct Message) 給使用者。
    
    用於緊急通知或在使用者忙碌時留言提醒。
    
    Args:
        user_name: 使用者名稱 (支援模糊匹配)
        message: 訊息內容
        
    Returns:
        成功與否的訊息
    """
    # 1. 解析 Discord ID
    discord_id = get_discord_id_by_name(user_name)
    if not discord_id:
        return f"錯誤：找不到用戶 '{user_name}' 的 Discord ID。"
    
    bot_token = settings.DISCORD_TOKEN
    if not bot_token:
        return "錯誤：Discord Token 未設定 (DISCORD_TOKEN)"

    # 2. 建立 DM Channel
    # Discord API: Create DM
    # POST /users/@me/channels
    api_base = "https://discord.com/api/v10"
    headers = {
        "Authorization": f"Bot {bot_token}",
        "Content-Type": "application/json"
    }
    
    try:
        # Create DM Channel
        dm_resp = requests.post(
            f"{api_base}/users/@me/channels",
            headers=headers,
            json={"recipient_id": str(discord_id)},  # 必須是 string
            timeout=10
        )
        
        if dm_resp.status_code not in (200, 201):
            return f"建立私訊頻道失敗: {dm_resp.status_code} - {dm_resp.text}"
            
        dm_channel_id = dm_resp.json().get("id")
        if not dm_channel_id:
            return "建立私訊頻道失敗: 無法取得 Channel ID"
            
        # 3. 發送訊息
        # POST /channels/{channel_id}/messages
        msg_resp = requests.post(
            f"{api_base}/channels/{dm_channel_id}/messages",
            headers=headers,
            json={"content": message},
            timeout=10
        )
        
        if msg_resp.status_code in (200, 201):
            return f"✅ 已成功私訊 {user_name}！"
        else:
            return f"發送私訊失敗: {msg_resp.status_code} - {msg_resp.text}"

    except Exception as e:
        return f"發送私訊時發生錯誤: {str(e)}"
