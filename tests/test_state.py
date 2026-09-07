from datetime import datetime


def test_ensure_file_creates_from_template_and_never_overwrites(plugin, home):
    st = plugin.state
    path = home / "MOOD.md"
    st.ensure_file(path)
    text = path.read_text()
    assert st.validate(text) is None
    assert "mood: calm" in text
    path.write_text("# Mood and relationship\n\nmood: hurt\n")
    st.ensure_file(path)
    assert "mood: hurt" in path.read_text()


def test_validate_rejects_missing_keys_and_bad_values(plugin, home):
    st = plugin.state
    good = st.TEMPLATE_PATH.read_text()
    assert st.validate(good) is None
    assert "missing keys" in st.validate("mood: calm\n")
    assert "bad mood" in st.validate(good.replace("mood: calm", "mood: ecstatic"))
    assert "bad warmth" in st.validate(good.replace("warmth: even", "warmth: lukewarm"))
    assert "too long" in st.validate(good.replace("warmth_reason: we have just met", "warmth_reason: " + "x" * 200))
    assert "fence" in st.validate("```\n" + good + "```")


def test_strip_fences(plugin):
    st = plugin.state
    inner = "# Mood and relationship\n\nmood: calm\n"
    assert st.strip_fences("```markdown\n" + inner + "```") == inner
    assert st.strip_fences(inner) == inner


def test_write_atomic_and_soul_excerpt(plugin, home):
    st = plugin.state
    path = home / "MOOD.md"
    st.write_atomic(path, "hello\n")
    assert path.read_text() == "hello\n"
    assert not [p for p in home.iterdir() if p.name.startswith(".mood-")]
    assert st.soul_excerpt().startswith("You are Jarvis")
    assert st.now_label(datetime(2026, 9, 7, 14, 5)) == "2026-09-07 14:05"
