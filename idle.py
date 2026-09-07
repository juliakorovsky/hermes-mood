"""Idle reflection: one Hermes cron job the plugin creates and keeps in sync with settings.

The job runs the main agent (so it speaks in the agent's own voice), reads MOOD.md and the
reflections file, and either writes one message or answers SILENT, which Hermes drops.
"""

from __future__ import annotations

import logging
from pathlib import Path

from . import state

logger = logging.getLogger(__name__)

JOB_NAME = "mood-idle-reflection"
IDLE_PROMPT_PATH = state.PLUGIN_DIR / "prompts" / "idle.md"


def render_prompt(mood_path: Path, reflections_path: Path) -> str:
    template = IDLE_PROMPT_PATH.read_text(encoding="utf-8")
    return template.format(mood_path=str(mood_path), reflections_path=str(reflections_path)).strip()


def _cron():
    from cron import jobs  # lazy: only present inside a Hermes install
    return jobs


def _main_model() -> tuple[str | None, str | None]:
    """Provider and model the user chats with, so the idle job is pinned and never fails closed."""
    try:
        from hermes_cli.config import load_config
        cfg = load_config() or {}
        model = cfg.get("model") or {}
        return model.get("provider") or None, model.get("default") or None
    except Exception:
        return None, None


def find_job(jobs_mod=None):
    jobs_mod = jobs_mod or _cron()
    for job in jobs_mod.list_jobs(include_disabled=True):
        if job.get("name") == JOB_NAME:
            return job
    return None


def ensure_job(*, enabled: bool, schedule: str, deliver: str, mood_path: Path, reflections_path: Path,
               provider: str | None = None, model: str | None = None, jobs_mod=None) -> str:
    """Create, update or remove the idle job to match settings. Returns what was done."""
    try:
        jobs_mod = jobs_mod or _cron()
    except Exception as exc:
        logger.warning("mood: cron unavailable, idle reflection not scheduled: %s", exc)
        return "unavailable"
    existing = find_job(jobs_mod)
    if not enabled:
        if existing:
            jobs_mod.remove_job(existing["id"])
            return "removed"
        return "disabled"
    if provider is None or model is None:
        cfg_provider, cfg_model = _main_model()
        provider = provider or cfg_provider
        model = model or cfg_model
    prompt = render_prompt(mood_path, reflections_path)
    if existing:
        changed = {k: v for k, v in {"prompt": prompt, "deliver": deliver, "provider": provider, "model": model}.items()
                   if existing.get(k) != v}
        if existing.get("schedule_display", existing.get("schedule")) != schedule:
            changed["schedule"] = schedule
        if changed:
            jobs_mod.update_job(existing["id"], changed)
            return "updated"
        return "unchanged"
    jobs_mod.create_job(prompt, schedule, name=JOB_NAME, deliver=deliver, provider=provider, model=model)
    return "created"
