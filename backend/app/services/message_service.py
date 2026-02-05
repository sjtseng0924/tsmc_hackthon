from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import desc, func, or_

from app.database import SessionLocal
from app.models import Message


def save_message(
    *,
    external_id: str,
    timestamp: Optional[datetime],
    user: Optional[str],
    role: Optional[str],
    content: str,
    knowledge_id: Optional[int] = None,
) -> None:
    if not external_id or not content:
        return
    db = SessionLocal()
    try:
        exists = db.query(Message.id).filter(Message.external_id == external_id).first()
        if exists:
            return
        msg = Message(
            external_id=external_id,
            timestamp=timestamp,
            user=user,
            role=role,
            content=content,
            knowledge_id=knowledge_id,
        )
        db.add(msg)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def list_recent_messages(limit: int = 20) -> list[Message]:
    limit = max(1, min(limit, 50))
    db = SessionLocal()
    try:
        return (
            db.query(Message)
            .order_by(desc(Message.timestamp), desc(Message.id))
            .limit(limit)
            .all()
        )
    finally:
        db.close()


def search_messages(query: str, limit: int = 20) -> list[Message]:
    limit = max(1, min(limit, 50))
    if not query:
        return []
    db = SessionLocal()
    try:
        q = f"%{query.strip().lower()}%"
        return (
            db.query(Message)
            .filter(
                or_(
                    func.lower(Message.content).like(q),
                    func.lower(Message.user).like(q),
                    func.lower(Message.role).like(q),
                )
            )
            .order_by(desc(Message.timestamp), desc(Message.id))
            .limit(limit)
            .all()
        )
    finally:
        db.close()
