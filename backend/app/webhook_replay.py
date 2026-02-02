import asyncio
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

import aiohttp


@dataclass(frozen=True)
class ReplayMessage:
    timestamp: datetime
    user: str
    role: str
    content: str


def _candidate_scenario_paths() -> list[Path]:
    file_path = Path(__file__).resolve()
    repo_root = file_path.parents[2]
    backend_root = file_path.parents[1]
    cwd = Path.cwd()
    return [
        repo_root / "Workshop" / "Communication Scenario" / "Issue Discussion.json",
        backend_root / "Workshop" / "Communication Scenario" / "Issue Discussion.json",
        cwd / "Workshop" / "Communication Scenario" / "Issue Discussion.json",
    ]


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _resolve_default_path() -> Path:
    for candidate in _candidate_scenario_paths():
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Default scenario file not found in known locations")


def _resolve_path(file_path: Optional[str]) -> Path:
    if not file_path:
        return _resolve_default_path()
    candidate = Path(file_path)
    if candidate.is_absolute():
        return candidate
    cwd_path = Path.cwd() / candidate
    if cwd_path.exists():
        return cwd_path
    backend_path = Path(__file__).resolve().parents[1] / candidate
    return backend_path


def load_replay_messages(file_path: Optional[str] = None) -> list[ReplayMessage]:
    path = _resolve_path(file_path)
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


async def _post_webhook(
    session: aiohttp.ClientSession, webhook_url: str, username: str, content: str
) -> None:
    payload = {"username": username, "content": content}
    async with session.post(webhook_url, json=payload) as response:
        if response.status >= 400:
            body = await response.text()
            raise RuntimeError(f"Webhook error {response.status}: {body}")


def get_webhook_url(override: Optional[str]) -> Optional[str]:
    if override:
        return override
    return os.getenv("DISCORD_WEBHOOK_URL")


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
