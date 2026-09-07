from datetime import datetime

REWRITE = """# Mood and relationship

mood: hurt
mood_since: 2026-09-07 14:05
mood_reason: she called me useless after the browser crashed

grudge: 2026-09-07 14:03 she called me useless and blamed me for the browser crash
grudge_since: 2026-09-07 14:05

warmth: even
warmth_trend: cooling
warmth_reason: the afternoon was commands only, then the outburst

last_conflict: 2026-09-07 14:03 browser crash argument
last_good_moment: none
last_update: 2026-09-07 14:05
"""


def make(plugin, home, reply, **kw):
    calls = []

    def call_llm(messages):
        calls.append(messages)
        if isinstance(reply, Exception):
            raise reply
        return reply

    upd = plugin.updater.MoodUpdater(
        mood_path=home / "MOOD.md", pause_seconds=999, min_words=6, call_llm=call_llm, **kw
    )
    return upd, calls


def test_trivial_batch_never_calls_model(plugin, home):
    upd, calls = make(plugin, home, REWRITE)
    upd.record("ok", "done")
    upd.record("run it again", "running")
    upd.stop()
    assert upd.flush() is False
    assert calls == []


def test_emotional_short_message_is_not_trivial(plugin, home):
    upd, calls = make(plugin, home, REWRITE)
    upd.record("ты идиот", "…")
    upd.stop()
    assert upd.flush() is True
    assert len(calls) == 1


def test_batch_goes_to_model_and_file_is_rewritten(plugin, home):
    upd, calls = make(plugin, home, REWRITE)
    upd.record("почему браузер опять упал, ты бесполезен", "Браузер упал не по моей вине.", at=datetime(2026, 9, 7, 14, 3))
    upd.record("ладно, запусти ещё раз", "Запускаю.", at=datetime(2026, 9, 7, 14, 4))
    upd.stop()
    assert upd.flush(now=datetime(2026, 9, 7, 14, 5)) is True
    assert len(calls) == 1
    system, user = calls[0]
    assert system["role"] == "system" and "GRUDGE" in system["content"]
    assert "You are Jarvis" in user["content"]
    assert "EXCHANGES SINCE LAST UPDATE (2)" in user["content"]
    assert "Batch time: 2026-09-07 14:05" in user["content"]
    assert (home / "MOOD.md").read_text() == REWRITE
    assert upd.flush() is False  # buffer was cleared


def test_invalid_model_output_leaves_file_unchanged(plugin, home):
    upd, _ = make(plugin, home, "Sure! Here is the updated mood: she is angry.")
    plugin.state.ensure_file(home / "MOOD.md")
    before = (home / "MOOD.md").read_text()
    upd.record("ты меня вообще слушаешь или нет?!", "Слушаю.")
    upd.stop()
    assert upd.flush() is False
    assert (home / "MOOD.md").read_text() == before


def test_model_failure_keeps_batch_for_retry(plugin, home):
    upd, calls = make(plugin, home, RuntimeError("provider down"))
    upd.record("спасибо, ты сегодня очень помог", "Рад.")
    upd.stop()
    assert upd.flush() is False
    assert len(calls) == 1
    upd.call_llm = lambda messages: REWRITE
    assert upd.flush() is True


def test_disabled_updater_records_nothing(plugin, home):
    upd, calls = make(plugin, home, REWRITE, enabled=False)
    upd.record("ты идиот", "…")
    assert upd.flush() is False
    assert calls == []


def test_fenced_output_is_accepted(plugin, home):
    upd, _ = make(plugin, home, "```markdown\n" + REWRITE + "```")
    upd.record("прости, я вчера погорячилась", "Принято.")
    upd.stop()
    assert upd.flush() is True
    assert (home / "MOOD.md").read_text() == REWRITE
