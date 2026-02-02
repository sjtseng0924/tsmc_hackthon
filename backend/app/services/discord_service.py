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
                # TODO: 接上 RAG/工具時，填入 rag_context
                result = await asyncio.to_thread(
                    run_agent,
                    user_message=prompt,
                    rag_context="",
                )

                reply = result.get("message") if isinstance(result, dict) else str(result)
                if not reply:
                    await message.channel.send("模型回覆為空，請再試一次或換個說法。")
                    return
                await message.channel.send(reply)
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
