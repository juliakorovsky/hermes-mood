"""Batch exchanges, wait for a pause, ask a cheap model to rewrite MOOD.md.

The buffer collects (user, assistant) pairs from ``post_llm_call``. Every new pair restarts a
timer; when the user has been quiet for ``pause_seconds`` the whole batch goes to the model in one
call. Trivial batches (short commands only) never reach the model.
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import state

logger = logging.getLogger(__name__)

UPDATE_PROMPT_PATH = state.PLUGIN_DIR / "prompts" / "update.md"
MAX_BATCH = 40           # pairs kept if flushes keep failing
MAX_TEXT_PER_TURN = 1500  # chars per side of an exchange sent to the model
_WORD_RE = re.compile(r"\S+")
_SHOUTING = re.compile(r"[!?]{2,}|[A-ZА-ЯЁ]{4,}")  # case-sensitive on purpose
_EMOTIONAL_WORDS = re.compile(
    r"\b(thank|thanks|sorry|love|hate|stupid|idiot|"
    r"спасибо|прости|извини|молодец|дурак|идиот|ненавижу|люблю|обид)",
    re.IGNORECASE,
)


@dataclass
class Exchange:
    user: str
    assistant: str
    at: datetime = field(default_factory=datetime.now)


def is_trivial(batch: list[Exchange], min_words: int) -> bool:
    """True when every user message is a short command with no emotional or personal content."""
    for ex in batch:
        words = len(_WORD_RE.findall(ex.user))
        if words >= min_words or _SHOUTING.search(ex.user) or _EMOTIONAL_WORDS.search(ex.user):
            return False
    return True


def _clip(text: str) -> str:
    text = (text or "").strip()
    return text if len(text) <= MAX_TEXT_PER_TURN else text[:MAX_TEXT_PER_TURN] + " […]"


def build_messages(batch: list[Exchange], current: str, soul: str, now: datetime) -> list[dict]:
    instructions = UPDATE_PROMPT_PATH.read_text(encoding="utf-8")
    lines = [f"[{ex.at.strftime('%H:%M')}] user: {_clip(ex.user)}\n[{ex.at.strftime('%H:%M')}] assistant: {_clip(ex.assistant)}"
             for ex in batch]
    user_content = (
        f"Batch time: {state.now_label(now)}\n\n"
        f"ASSISTANT PERSONA (SOUL.md excerpt):\n---\n{soul}\n---\n\n"
        f"CURRENT FILE:\n---\n{current.strip()}\n---\n\n"
        f"EXCHANGES SINCE LAST UPDATE ({len(batch)}):\n" + "\n\n".join(lines)
    )
    return [{"role": "system", "content": instructions}, {"role": "user", "content": user_content}]


class MoodUpdater:
    def __init__(self, *, mood_path: Path, pause_seconds: float, min_words: int,
                 call_llm: Callable[[list[dict]], str], enabled: bool = True) -> None:
        self.mood_path = mood_path
        self.pause_seconds = pause_seconds
        self.min_words = min_words
        self.call_llm = call_llm
        self.enabled = enabled
        self._batch: list[Exchange] = []
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None

    # -- recording ------------------------------------------------------------------------------

    def record(self, user: str, assistant: str, *, at: datetime | None = None) -> None:
        if not self.enabled or not (user or "").strip():
            return
        with self._lock:
            self._batch.append(Exchange(user, assistant or "", at or datetime.now()))
            del self._batch[:-MAX_BATCH]
            self._restart_timer_locked()

    def _restart_timer_locked(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
        self._timer = threading.Timer(self.pause_seconds, self.flush)
        self._timer.daemon = True
        self._timer.start()

    def stop(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

    # -- flushing --------------------------------------------------------------------------------

    def flush(self, *, now: datetime | None = None) -> bool:
        """Send the pending batch to the model and rewrite MOOD.md. Returns True if the file changed."""
        with self._lock:
            batch, self._batch = self._batch, []
            self._timer = None
        if not batch:
            return False
        if is_trivial(batch, self.min_words):
            logger.info("mood: batch of %d trivial exchanges skipped", len(batch))
            return False
        state.ensure_file(self.mood_path)
        current = state.read(self.mood_path)
        messages = build_messages(batch, current, state.soul_excerpt(), now or datetime.now())
        try:
            raw = self.call_llm(messages)
        except Exception as exc:  # provider down, trust gate, timeout: keep the batch for next time
            logger.warning("mood: model call failed, batch kept: %s", exc)
            with self._lock:
                self._batch = batch + self._batch
                del self._batch[:-MAX_BATCH]
            return False
        text = state.strip_fences(raw or "")
        error = state.validate(text)
        if error:
            logger.warning("mood: rejected model output (%s); file unchanged", error)
            return False
        state.write_atomic(self.mood_path, text)
        logger.info("mood: MOOD.md updated from %d exchanges", len(batch))
        return True
