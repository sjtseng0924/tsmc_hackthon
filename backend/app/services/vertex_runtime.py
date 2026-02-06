import os
import threading
from contextlib import contextmanager
from typing import Callable, TypeVar

import vertexai

from app.config import settings

T = TypeVar("T")

_VERTEX_CALL_LOCK = threading.RLock()


def _apply_credentials() -> None:
    creds_path = settings.GOOGLE_APPLICATION_CREDENTIALS
    if creds_path:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path


def _init_vertex(location: str | None) -> None:
    _apply_credentials()
    vertexai.init(
        project=settings.VERTEX_PROJECT,
        location=location,
    )


def init_agent_vertex() -> None:
    _init_vertex(settings.VERTEX_AGENT_LOCATION)


def init_embedding_vertex() -> None:
    _init_vertex(settings.VERTEX_EMBEDDING_LOCATION)


@contextmanager
def vertex_call_lock():
    with _VERTEX_CALL_LOCK:
        yield


def run_with_embedding_context(func: Callable[[], T]) -> T:
    with _VERTEX_CALL_LOCK:
        init_embedding_vertex()
        try:
            return func()
        finally:
            # Reset to agent context after embedding calls so next LLM call
            # does not accidentally inherit embedding location.
            init_agent_vertex()
