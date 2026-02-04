import asyncio
import contextlib
import json
import logging
from typing import Optional

import discord

# Gemini 相關導入
try:
    from app.services.gemini import run_agent
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from app.config import settings
from app.services.message_service import save_message

class DiscordServiceError(Exception):
    pass


class DiscordNotInitialized(DiscordServiceError):
    pass


class DiscordNotReady(DiscordServiceError):
    pass


class DiscordChannelNotFound(DiscordServiceError):
    pass


class DiscordMissingPermissions(DiscordServiceError):
    pass


class DiscordInvalidChannel(DiscordServiceError):
    pass


def _get_token() -> Optional[str]:
    return settings.DISCORD_TOKEN


def _build_discord_client(intents: discord.Intents) -> discord.Client:
    return discord.Client(intents=intents)


def _strip_bot_mention(message: discord.Message, bot_user: discord.ClientUser) -> str:
    content = message.content or ""
    if bot_user:
        mention = f"<@{bot_user.id}>"
        mention_nick = f"<@!{bot_user.id}>"
        content = content.replace(mention, "").replace(mention_nick, "")
    return content.strip()


async def _run_discord_client(
    client: discord.Client, token: str, logger: logging.Logger
) -> None:
    try:
        await client.start(token)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Discord client stopped unexpectedly")


class DiscordService:
    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger
        self._token = _get_token()
        self._client: Optional[discord.Client] = None
        self._task: Optional[asyncio.Task] = None
        self._history: dict[int, list[dict]] = {}

    @property
    def client(self) -> Optional[discord.Client]:
        return self._client

    def is_ready(self) -> bool:
        return bool(self._client and self._client.is_ready())

    async def startup(self) -> None:
        if not self._token:
            self._logger.warning("DISCORD_TOKEN not set; Discord client will not start")
            return

        intents = discord.Intents.default()
        intents.message_content = True
        client = _build_discord_client(intents)

        @client.event
        async def on_ready() -> None:
            self._logger.info("Discord client logged in as %s", client.user)

        @client.event
        async def on_message(message: discord.Message) -> None:
            if message.author == client.user:
                return
            if client.user is None:
                return
            if client.user not in message.mentions:
                return
            if not message.content:
                return

            prompt = _strip_bot_mention(message, client.user)
            if not prompt:
                await message.channel.send("請輸入要詢問的內容。")
                return

            if not GEMINI_AVAILABLE:
                await message.channel.send("Gemini Agent 目前無法使用。")
                return

            try:
                channel_id = message.channel.id
                self._append_history(channel_id, "user", prompt)
                save_message(
                    external_id=str(message.id),
                    timestamp=message.created_at,
                    user=str(message.author),
                    role="user",
                    content=prompt,
                )

                await self._dispatch_agent_reply(
                    channel_id=channel_id,
                    user_prompt=prompt,
                    client=client,
                    channel=message.channel,
                )
            except Exception:
                self._logger.exception("Gemini reply failed")
                await message.channel.send("發生錯誤，請稍後再試。")

        self._client = client
        self._task = asyncio.create_task(
            _run_discord_client(client, self._token, self._logger)
        )

    async def shutdown(self) -> None:
        if self._client is not None:
            await self._client.close()

        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def send_message(self, channel_id: int, content: str) -> discord.Message:
        if self._client is None:
            raise DiscordNotInitialized("Discord client not initialized")
        if not self._client.is_ready():
            raise DiscordNotReady("Discord client not ready")

        try:
            channel = await self._client.fetch_channel(channel_id)
        except discord.NotFound as exc:
            raise DiscordChannelNotFound("Channel not found") from exc
        except discord.Forbidden as exc:
            raise DiscordMissingPermissions("Missing permissions for channel") from exc

        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            raise DiscordInvalidChannel("Channel is not text-capable")

        return await channel.send(content)

    async def _run_solution_loop(
        self,
        *,
        channel_id: int,
        user_prompt: str,
        client: discord.Client,
        channel: discord.abc.Messageable,
    ) -> None:
        max_turns = 4
        current_prompt = user_prompt
        for idx in range(max_turns):
            result = await asyncio.to_thread(
                run_agent,
                user_message=current_prompt,
                rag_context="",
                conversation_history=self._get_history(channel_id),
            )

            if not isinstance(result, dict):
                reply = str(result)
                await self._send_reply(channel_id, client, channel, reply)
                return

            mode = result.get("mode")
            structured = result.get("structured")
            reply = result.get("message")

            if mode == "solution" and isinstance(structured, dict):
                updates = structured.get("updates") or structured.get("progress") or []
                for line in updates:
                    if line:
                        await channel.send(str(line))

                reply_text = structured.get("reply", "")
                if reply_text and structured.get("status", "final") == "final":
                    await self._send_reply(channel_id, client, channel, reply_text)

                status = structured.get("status", "final")
                if status != "continue":
                    return

                self._append_history(channel_id, "user", "繼續")
                current_prompt = "繼續"
                continue

            if not reply:
                await channel.send("模型回覆為空，請再試一次或換個說法。")
                return

            updates, status, summary = _extract_solution_text(reply)
            for line in updates:
                await channel.send(line)

            if status == "continue":
                self._append_history(channel_id, "user", "繼續")
                current_prompt = "繼續"
                continue

            if summary:
                await self._send_reply(channel_id, client, channel, summary)
                return

            progress_lines, final_reply = _split_progress_lines(reply)
            for line in progress_lines:
                await channel.send(line)
            if final_reply:
                await self._send_reply(channel_id, client, channel, final_reply)
            return

        await channel.send("已達到最大查詢輪數，若需繼續請再描述需求。")

    async def _dispatch_agent_reply(
        self,
        *,
        channel_id: int,
        user_prompt: str,
        client: discord.Client,
        channel: discord.abc.Messageable,
    ) -> None:
        result = await asyncio.to_thread(
            run_agent,
            user_message=user_prompt,
            rag_context="",
            conversation_history=self._get_history(channel_id),
        )

        if not isinstance(result, dict):
            await self._send_reply(channel_id, client, channel, str(result))
            return

        mode = result.get("mode")
        reply = result.get("message") or ""

        if mode == "solution":
            await self._run_solution_loop(
                channel_id=channel_id,
                user_prompt=user_prompt,
                client=client,
                channel=channel,
            )
            return

        if not reply:
            await channel.send("模型回覆為空，請再試一次或換個說法。")
            return

        await self._send_reply(channel_id, client, channel, reply)

    async def _send_reply(
        self,
        channel_id: int,
        client: discord.Client,
        channel: discord.abc.Messageable,
        content: str,
    ) -> None:
        for chunk in _chunk_message(content):
            bot_msg = await channel.send(chunk)
            self._append_history(channel_id, "assistant", chunk)
            save_message(
                external_id=str(bot_msg.id),
                timestamp=bot_msg.created_at,
                user=str(client.user),
                role="assistant",
                content=chunk,
            )

    def _append_history(self, channel_id: int, role: str, content: str) -> None:
        items = self._history.setdefault(channel_id, [])
        items.append({"role": role, "content": content})
        if len(items) > 30:
            self._history[channel_id] = items[-30:]

    def _get_history(self, channel_id: int) -> list[dict]:
        return list(self._history.get(channel_id, []))


def _split_progress_lines(reply: str) -> tuple[list[str], str]:
    progress_lines = []
    final_lines = []
    for line in (reply or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("目前在看") or stripped.startswith("進度:") or stripped.startswith("[進度]"):
            progress_lines.append(stripped)
        else:
            final_lines.append(line)
    return progress_lines, "\n".join(final_lines).strip()


def _extract_solution_text(reply: str) -> tuple[list[str], str, str]:
    updates: list[str] = []
    summary_lines: list[str] = []
    status = "final"
    in_summary = False
    status_line_text = ""

    content = reply or ""
    json_payload = _try_parse_json(content)
    if isinstance(json_payload, dict):
        raw_updates = json_payload.get("updates") or json_payload.get("progress") or []
        updates.extend([str(item) for item in raw_updates if item])
        summary = str(json_payload.get("reply") or "").strip()
        status = str(json_payload.get("status") or "final").lower()
        return updates, status, summary

    if "[[CONTINUE]]" in content:
        status = "continue"
        content = content.replace("[[CONTINUE]]", "").strip()

    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            continue
        lowered = line.lower()
        if line.startswith("目前在看:") or line.startswith("原因:") or line.startswith("下一步:"):
            updates.append(line)
            continue
        if lowered.startswith("狀態:"):
            updates.append(line)
            status_line_text = line.split(":", 1)[1].strip().lower()
            continue
        if line.startswith("總結:") or line.startswith("結論:"):
            in_summary = True
            summary_lines.append(line.split(":", 1)[1].strip())
            continue
        if in_summary:
            summary_lines.append(raw)
        else:
            summary_lines.append(raw)

    summary = "\n".join(summary_lines).strip()
    if status_line_text and "繼續" in status_line_text:
        status = "continue"
    return updates, status, summary


def _chunk_message(content: str, limit: int = 1900) -> list[str]:
    if not content:
        return [""]
    if len(content) <= limit:
        return [content]
    chunks = []
    remaining = content
    while len(remaining) > limit:
        split_at = remaining.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip("\n")
    if remaining:
        chunks.append(remaining)
    return chunks


def _try_parse_json(content: str) -> Optional[dict]:
    text = (content or "").strip()
    if not text.startswith("{"):
        return None
    try:
        data = json.loads(text)
    except Exception:
        return None
    return data if isinstance(data, dict) else None
