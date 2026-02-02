import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from typing import Iterable, Optional

import aiohttp

from app.config import settings


@dataclass(frozen=True)
class ReplayMessage:
    timestamp: datetime
    user: str
    role: str
    content: str


def _scenario_paths() -> Path:
    repo_root = Path(settings.BACKEND_ROOT)
    return repo_root / "Workshop" / "CommunicationScenario" / "IssueDiscussion.json"


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def load_replay_messages(file_path: Optional[str] = None) -> list[ReplayMessage]:
    path = _scenario_paths() if file_path is None else Path(file_path)
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)

    messages: list[ReplayMessage] = []
    for item in raw:
        messages.append(
            ReplayMessage(
                timestamp=_parse_timestamp(item["timestamp"]),
                user=item.get("user", "Unknown"),
                role=item.get("role", ""),
                content=item.get("message", ""),
            )
        )
    return messages


def format_username(message: ReplayMessage, with_role: bool) -> str:
    if with_role and message.role:
        return f"{message.user} ({message.role})"
    return message.user


def _inject_bot_mention(content: str) -> str:
    bot_id = settings.DISCORD_BOT_ID
    if not bot_id:
        return content
    mention = f"<@{bot_id}>"
    if mention in content or f"<@!{bot_id}>" in content:
        return content
    bot_name = settings.DISCORD_BOT_NAME
    if bot_name:
        return content.replace(f"@{bot_name}", mention)
    return content


def _avatar_url_for_user(user: str) -> str:
    seed = quote(user.strip() or "Unknown")
    return f"https://api.dicebear.com/7.x/identicon/png?seed={seed}"


async def _post_webhook(
    session: aiohttp.ClientSession, webhook_url: str, username: str, content: str
) -> None:
    content = _inject_bot_mention(content)
    payload = {
        "username": username,
        "content": content,
        "avatar_url": _avatar_url_for_user(username),
    }
    if settings.DISCORD_BOT_ID:
        payload["allowed_mentions"] = {"users": [str(settings.DISCORD_BOT_ID)]}
    async with session.post(webhook_url, json=payload) as response:
        if response.status >= 400:
            body = await response.text()
            raise RuntimeError(f"Webhook error {response.status}: {body}")


def get_webhook_url(override: Optional[str]) -> Optional[str]:
    if override:
        return override
    return settings.DISCORD_WEBHOOK_URL


async def replay_via_webhook(
    webhook_url: str,
    messages: Iterable[ReplayMessage],
    paced: bool,
    max_delay_seconds: float,
    include_role: bool,
) -> int:
    async with aiohttp.ClientSession() as session:
        sent = 0
        previous_time: Optional[datetime] = None
        for message in messages:
            if paced and previous_time is not None:
                delay = (message.timestamp - previous_time).total_seconds()
                await asyncio.sleep(min(max(delay, 0.0), max_delay_seconds))

            username = format_username(message, include_role)
            await _post_webhook(session, webhook_url, username, message.content)
            sent += 1
            previous_time = message.timestamp
        return sent
