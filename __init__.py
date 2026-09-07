"""hermes-mood: mood, grudges and warmth for a Hermes agent.

Hooks:
  pre_llm_call   inject the persona note and MOOD.md into the turn
  post_llm_call  buffer the exchange; a pause in conversation triggers one model call that rewrites MOOD.md

On register the plugin also makes sure the idle-reflection cron job exists (or is removed when disabled).

Settings live under ``plugins.entries.hermes-mood.settings`` in config.yaml; every one has an env override.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from . import idle, state
from .updater import MoodUpdater

logger = logging.getLogger(__name__)

AUX_TASK = "hermes_mood_update"
PERSONA_PROMPT_PATH = state.PLUGIN_DIR / "prompts" / "persona.md"

DEFAULTS = {
    "pause_seconds": 180,
    "min_words": 6,
    "update_enabled": True,
    "update_provider": "openrouter",
    "update_model": "anthropic/claude-haiku-4.5",
    "idle_enabled": True,
    "idle_schedule": "0 10,14,18,22 * * *",
    "idle_deliver": "telegram",
    "idle_provider": None,
    "idle_model": None,
    "mood_file": "MOOD.md",
    "reflections_file": "reflections.md",
}
ENV_PREFIX = "HERMES_MOOD_"


def _setting(ctx, key: str):
    env = os.environ.get(ENV_PREFIX + key.upper())
    if env is not None and env != "":
        default = DEFAULTS[key]
        if isinstance(default, bool):
            return env.strip().lower() not in {"0", "false", "no", "off"}
        if isinstance(default, int):
            try:
                return int(env)
            except ValueError:
                return default
        return env
    try:
        value = ctx.get_config(key, None)
    except Exception:
        value = None
    return DEFAULTS[key] if value is None else value


def _resolve_path(name: str) -> Path:
    p = Path(name)
    return p if p.is_absolute() else state.hermes_home() / p


def register(ctx):
    mood_path = _resolve_path(_setting(ctx, "mood_file"))
    reflections_path = _resolve_path(_setting(ctx, "reflections_file"))
    state.ensure_file(mood_path)
    persona = PERSONA_PROMPT_PATH.read_text(encoding="utf-8").strip()

    # -- cheap model for the rewrite: its own auxiliary slot, overridable in auxiliary.<task> -----
    try:
        ctx.register_auxiliary_task(
            AUX_TASK, display_name="Mood update",
            description="Rewrites MOOD.md after a pause in conversation.",
            defaults={"provider": _setting(ctx, "update_provider"), "model": _setting(ctx, "update_model")},
        )
        task = AUX_TASK
    except Exception as exc:
        logger.warning("mood: auxiliary task not registered, using the main model: %s", exc)
        task = None

    def call_llm(messages):
        kwargs = {"messages": messages, "max_tokens": 700, "temperature": 0.3, "purpose": "mood.update"}
        if task:
            kwargs["task"] = task
        return ctx.llm.complete(**kwargs).text

    updater = MoodUpdater(
        mood_path=mood_path,
        pause_seconds=float(_setting(ctx, "pause_seconds")),
        min_words=int(_setting(ctx, "min_words")),
        call_llm=call_llm,
        enabled=bool(_setting(ctx, "update_enabled")),
    )

    # -- hooks ----------------------------------------------------------------------------------
    def on_pre_llm_call(**kwargs):
        text = state.read(mood_path).strip()
        if not text:
            return None
        return {"context": f"{persona}\n\n{text}"}

    def on_post_llm_call(user_message: str = "", assistant_response: str = "", **kwargs):
        updater.record(user_message, assistant_response)

    ctx.register_hook("pre_llm_call", on_pre_llm_call)
    ctx.register_hook("post_llm_call", on_post_llm_call)

    # -- idle reflection cron -------------------------------------------------------------------
    try:
        outcome = idle.ensure_job(
            enabled=bool(_setting(ctx, "idle_enabled")),
            schedule=str(_setting(ctx, "idle_schedule")),
            deliver=str(_setting(ctx, "idle_deliver")),
            mood_path=mood_path,
            reflections_path=reflections_path,
            provider=_setting(ctx, "idle_provider"),
            model=_setting(ctx, "idle_model"),
        )
        logger.info("mood: idle reflection job %s", outcome)
    except Exception as exc:
        logger.warning("mood: could not set up idle reflection: %s", exc)

    return updater
