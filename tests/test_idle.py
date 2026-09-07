from pathlib import Path


def test_render_prompt_substitutes_paths(plugin):
    text = plugin.idle.render_prompt(Path("/x/MOOD.md"), Path("/x/reflections.md"))
    assert "/x/MOOD.md" in text and "/x/reflections.md" in text
    assert text.endswith("SILENT")


def test_ensure_job_creates_pinned_job(plugin, fake_jobs):
    jobs = fake_jobs()
    out = plugin.idle.ensure_job(
        enabled=True, schedule="0 10,14,18,22 * * *", deliver="telegram",
        mood_path=Path("/h/MOOD.md"), reflections_path=Path("/h/reflections.md"),
        provider="openrouter", model="anthropic/claude-haiku-4.5", jobs_mod=jobs,
    )
    assert out == "created"
    job = jobs.created[0]
    assert job["name"] == plugin.idle.JOB_NAME
    assert job["deliver"] == "telegram"
    assert job["provider"] == "openrouter" and job["model"] == "anthropic/claude-haiku-4.5"
    assert "/h/MOOD.md" in job["prompt"]


def test_ensure_job_is_idempotent_and_updates_on_change(plugin, fake_jobs):
    jobs = fake_jobs()
    common = dict(enabled=True, schedule="0 10 * * *", deliver="telegram",
                  mood_path=Path("/h/MOOD.md"), reflections_path=Path("/h/reflections.md"),
                  provider="openrouter", model="m", jobs_mod=jobs)
    assert plugin.idle.ensure_job(**common) == "created"
    assert plugin.idle.ensure_job(**common) == "unchanged"
    assert plugin.idle.ensure_job(**{**common, "deliver": "discord"}) == "updated"
    assert jobs.updated[-1][1] == {"deliver": "discord"}


def test_ensure_job_removes_when_disabled(plugin, fake_jobs):
    jobs = fake_jobs([{"id": "old1", "name": plugin.idle.JOB_NAME}])
    out = plugin.idle.ensure_job(
        enabled=False, schedule="x", deliver="telegram",
        mood_path=Path("/h/MOOD.md"), reflections_path=Path("/h/reflections.md"), jobs_mod=jobs,
    )
    assert out == "removed" and jobs.removed == ["old1"]
