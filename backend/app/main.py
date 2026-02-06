import logging
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import settings
from app.services.discord_service import (
    DiscordChannelNotFound,
    DiscordInvalidChannel,
    DiscordMissingPermissions,
    DiscordNotInitialized,
    DiscordNotReady,
    DiscordService,
)
from app.api import cases_router
from app.api.contacts import router as contacts_router
from app.api.discord import router as discord_router
from app.services.webhook_replay import get_webhook_url, load_replay_messages, replay_via_webhook
# Gemini 相關導入
try:
    from app.services.gemini import run_agent
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord-backend")

app = FastAPI(title="Discord Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(cases_router)
app.include_router(contacts_router)
app.include_router(discord_router)


class DiscordSendRequest(BaseModel):
    channel_id: int = Field(..., description="Target Discord channel ID")
    content: str = Field(..., min_length=1, max_length=2000)


class DiscordSendResponse(BaseModel):
    message_id: int
    channel_id: int


class WebhookReplayRequest(BaseModel):
    scenario: int = Field(..., ge=1, le=3, description="Scenario number (1-3)")
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
    channel_id: Optional[int] = Field(
        default=None, description="Discord channel ID (for log/message scoping)"
    )
    parent_channel_id: Optional[int] = Field(
        default=None, description="Parent channel ID if using threads"
    )


class GeminiAgentResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


@app.on_event("startup")
async def startup_event() -> None:
    service = DiscordService(logger)
    await service.startup()
    app.state.discord_service = service


@app.on_event("shutdown")
async def shutdown_event() -> None:
    service: DiscordService = getattr(app.state, "discord_service", None)
    if service is not None:
        await service.shutdown()


@app.get("/health")
async def health_check() -> dict:
    service: DiscordService = getattr(app.state, "discord_service", None)
    return {
        "status": "ok",
        "discord_ready": bool(service and service.is_ready()),
    }


@app.post("/discord/send", response_model=DiscordSendResponse)
async def send_discord_message(payload: DiscordSendRequest) -> DiscordSendResponse:
    service: DiscordService = getattr(app.state, "discord_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Discord service not initialized")

    try:
        message = await service.send_message(payload.channel_id, payload.content)
    except DiscordNotInitialized as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DiscordNotReady as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DiscordChannelNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DiscordMissingPermissions as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except DiscordInvalidChannel as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return DiscordSendResponse(message_id=message.id, channel_id=message.channel.id)


@app.post("/discord/webhook/replay", response_model=WebhookReplayResponse)
async def replay_webhook(payload: WebhookReplayRequest) -> WebhookReplayResponse:
    webhook_url = get_webhook_url(scenario=payload.scenario)
    if not webhook_url:
        raise HTTPException(status_code=400, detail="Webhook URL not provided")

    try:
        messages = load_replay_messages(payload.scenario)
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

        if payload.channel_id is not None:
            from app.services import assistant_tools
            from app.services.discord_service import _context_channel_id

            context_channel_id = _context_channel_id(
                payload.channel_id, payload.parent_channel_id
            )
            assistant_tools.set_log_context(context_channel_id)

        result = run_agent(
            user_message=payload.user_message,
            rag_context=payload.rag_context,
        )

        if payload.channel_id is not None:
            assistant_tools.set_log_context(None)

        return GeminiAgentResponse(success=True, data=result)

    except Exception as e:
        if payload.channel_id is not None:
            from app.services import assistant_tools

            assistant_tools.set_log_context(None)
        logger.error(f"Gemini Agent 錯誤: {str(e)}")
        return GeminiAgentResponse(success=False, error=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=False)
