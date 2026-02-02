import asyncio
import contextlib
import logging
from typing import Optional

import discord

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
            if message.content:
                author_name = message.author.display_name
                author_id = message.author.id
                await message.channel.send(
                    f"{author_name} ({author_id}) 說：{message.content}"
                )

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
