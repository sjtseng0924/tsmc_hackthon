import asyncio
import contextlib
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
from app.services import assistant_tools
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
        self._loop: Optional[asyncio.AbstractEventLoop] = None

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
        self._loop = asyncio.get_running_loop()

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
                assistant_tools.set_progress_sender(
                    _make_progress_sender(self, channel_id, self._loop)
                )
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
            finally:
                assistant_tools.set_progress_sender(None)

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
        result = await asyncio.to_thread(
            run_agent,
            user_message=user_prompt,
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
            reply_text = structured.get("reply", "")
            if reply_text:
                await self._send_reply(channel_id, client, channel, reply_text)
                return

        if not reply:
            await channel.send("模型回覆為空，請再試一次或換個說法。")
            return

        await self._send_reply(channel_id, client, channel, reply)

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


def _make_progress_sender(
    service: "DiscordService",
    channel_id: int,
    loop: Optional[asyncio.AbstractEventLoop],
):
    def _send(message: str) -> None:
        if not loop or not service:
            return
        try:
            asyncio.run_coroutine_threadsafe(
                service.send_message(channel_id, message),
                loop,
            )
        except Exception:
            return

    return _send
