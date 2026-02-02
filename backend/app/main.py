import asyncio
import contextlib
import logging
import os
from typing import Literal, Optional

import discord
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.webhook_replay import get_webhook_url, load_replay_messages, replay_via_webhook
# Gemini 相關導入
try:
    from app.gemini import run_agent
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

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


class WebhookReplayRequest(BaseModel):
    webhook_url: Optional[str] = Field(
        default=None, description="Discord webhook URL (fallback to DISCORD_WEBHOOK_URL)"
    )
    file_path: Optional[str] = Field(
        default=None, description="Path to scenario JSON file"
    )
    mode: Literal["instant", "paced"] = Field(
        default="instant", description="Send all messages instantly or paced"
    )
    max_delay_seconds: float = Field(
        default=2.0, ge=0.0, le=30.0, description="Cap delay when paced"
    )
    username_with_role: bool = Field(
        default=True, description="Append role in webhook username"
    )


class WebhookReplayResponse(BaseModel):
    sent: int


class GeminiAgentRequest(BaseModel):
    user_message: str = Field(..., description="使用者訊息")
    rag_context: str = Field(default="", description="RAG 上下文")


class GeminiAgentResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


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


@app.post("/discord/webhook/replay", response_model=WebhookReplayResponse)
async def replay_webhook(payload: WebhookReplayRequest) -> WebhookReplayResponse:
    webhook_url = get_webhook_url(payload.webhook_url)
    if not webhook_url:
        raise HTTPException(status_code=400, detail="Webhook URL not provided")

    try:
        messages = load_replay_messages(payload.file_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Scenario file not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid scenario data") from exc

    paced = payload.mode == "paced"
    try:
        sent = await replay_via_webhook(
            webhook_url=webhook_url,
            messages=messages,
            paced=paced,
            max_delay_seconds=payload.max_delay_seconds,
            include_role=payload.username_with_role,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return WebhookReplayResponse(sent=sent)


@app.post("/agent", response_model=GeminiAgentResponse)
async def agent_handler(payload: GeminiAgentRequest) -> GeminiAgentResponse:
    """呼叫 Gemini Agent"""
    if not GEMINI_AVAILABLE:
        raise HTTPException(status_code=503, detail="Gemini Agent not available")

    try:
        logger.info(f"收到訊息: {payload.user_message}")

        result = run_agent(
            user_message=payload.user_message,
            rag_context=payload.rag_context,
        )

        return GeminiAgentResponse(success=True, data=result)

    except Exception as e:
        logger.error(f"Gemini Agent 錯誤: {str(e)}")
        return GeminiAgentResponse(success=False, error=str(e))


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
