import asyncio
import contextlib
import logging
import os
from typing import Optional

import discord
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

load_dotenv(override=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord-backend")

app = FastAPI(title="Discord Backend")


def _build_discord_client() -> discord.Client:
    intents = discord.Intents.default()
    intents.message_content = True
    return discord.Client(intents=intents)


class DiscordSendRequest(BaseModel):
    channel_id: int = Field(..., description="Target Discord channel ID")
    content: str = Field(..., min_length=1, max_length=2000)


class DiscordSendResponse(BaseModel):
    message_id: int
    channel_id: int


def _get_token() -> Optional[str]:
    return os.getenv("DISCORD_TOKEN")


async def _run_discord_client(client: discord.Client, token: str) -> None:
    try:
        await client.start(token)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Discord client stopped unexpectedly")


@app.on_event("startup")
async def startup_event() -> None:
    token = _get_token()
    if not token:
        logger.warning("DISCORD_TOKEN not set; Discord client will not start")
        app.state.discord_client = None
        app.state.discord_task = None
        return

    client = _build_discord_client()

    @client.event
    async def on_ready() -> None:
        logger.info("Discord client logged in as %s", client.user)

    @client.event
    async def on_message(message: discord.Message) -> None:
        if message.author == client.user:
            return
        if message.content:
            author_name = message.author.display_name
            author_id = message.author.id
            await message.channel.send(f"{author_name} ({author_id}) 說：{message.content}")

    app.state.discord_client = client
    app.state.discord_task = asyncio.create_task(_run_discord_client(client, token))


@app.on_event("shutdown")
async def shutdown_event() -> None:
    client: Optional[discord.Client] = getattr(app.state, "discord_client", None)
    task: Optional[asyncio.Task] = getattr(app.state, "discord_task", None)

    if client is not None:
        await client.close()

    if task is not None:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@app.get("/health")
async def health_check() -> dict:
    client: Optional[discord.Client] = getattr(app.state, "discord_client", None)
    return {
        "status": "ok",
        "discord_ready": bool(client and client.is_ready()),
    }


@app.post("/discord/send", response_model=DiscordSendResponse)
async def send_discord_message(payload: DiscordSendRequest) -> DiscordSendResponse:
    client: Optional[discord.Client] = getattr(app.state, "discord_client", None)
    if client is None:
        raise HTTPException(status_code=503, detail="Discord client not initialized")

    if not client.is_ready():
        raise HTTPException(status_code=503, detail="Discord client not ready")

    try:
        channel = await client.fetch_channel(payload.channel_id)
    except discord.NotFound as exc:
        raise HTTPException(status_code=404, detail="Channel not found") from exc
    except discord.Forbidden as exc:
        raise HTTPException(status_code=403, detail="Missing permissions for channel") from exc
    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        raise HTTPException(status_code=400, detail="Channel is not text-capable")

    message = await channel.send(payload.content)
    return DiscordSendResponse(message_id=message.id, channel_id=channel.id)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
