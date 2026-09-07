def test_register_wires_hooks_and_injects_mood(plugin, home, fake_ctx, monkeypatch):
    monkeypatch.setattr(plugin.idle, "ensure_job", lambda **kw: "unavailable")
    ctx = fake_ctx(reply="")
    updater = plugin.register(ctx)
    assert set(ctx.hooks) == {"pre_llm_call", "post_llm_call"}
    assert ctx.aux[0][0] == plugin.AUX_TASK
    assert ctx.aux[0][1]["defaults"]["model"] == "anthropic/claude-haiku-4.5"
    assert (home / "MOOD.md").exists()
    ctx_out = ctx.hooks["pre_llm_call"](session_id="s", user_message="hi")
    assert ctx_out["context"].startswith("[Mood]")
    assert "mood: calm" in ctx_out["context"]
    ctx.hooks["post_llm_call"](user_message="ты идиот", assistant_response="…")
    updater.stop()
    assert len(updater._batch) == 1


def test_env_overrides_settings(plugin, home, fake_ctx, monkeypatch):
    monkeypatch.setattr(plugin.idle, "ensure_job", lambda **kw: "unavailable")
    monkeypatch.setenv("HERMES_MOOD_PAUSE_SECONDS", "42")
    monkeypatch.setenv("HERMES_MOOD_UPDATE_ENABLED", "0")
    monkeypatch.setenv("HERMES_MOOD_MOOD_FILE", "custom/state.md")
    updater = plugin.register(fake_ctx())
    assert updater.pause_seconds == 42
    assert updater.enabled is False
    assert updater.mood_path == home / "custom" / "state.md"
    assert updater.mood_path.exists()


def test_call_llm_uses_registered_task(plugin, home, fake_ctx, monkeypatch):
    monkeypatch.setattr(plugin.idle, "ensure_job", lambda **kw: "unavailable")
    ctx = fake_ctx(reply="whatever")
    updater = plugin.register(ctx)
    updater.call_llm([{"role": "user", "content": "x"}])
    assert ctx.llm.calls[0]["task"] == plugin.AUX_TASK
    assert ctx.llm.calls[0]["purpose"] == "mood.update"
