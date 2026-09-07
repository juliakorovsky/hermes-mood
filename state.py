"""MOOD.md: read, validate, write atomically.

The file is plain ``key: value`` lines grouped by blank lines. It is the only state this plugin
owns. The model rewrites it as a whole; we only check that the rewrite kept the contract.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = PLUGIN_DIR / "templates" / "MOOD.md"

REQUIRED_KEYS = (
    "mood", "mood_since", "mood_reason",
    "grudge", "grudge_since",
    "warmth", "warmth_trend", "warmth_reason",
    "last_conflict", "last_good_moment", "last_update",
)
MOODS = {"calm", "content", "curious", "tired", "irritated", "hurt", "withdrawn"}
WARMTHS = {"warm", "even", "cool", "cold"}
TRENDS = {"warming", "steady", "cooling"}
MAX_VALUE_LEN = 160


def hermes_home() -> Path:
    """$HERMES_HOME, else ~/.hermes. Resolved at call time so tests can override it."""
    return Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))


def now_label(now: datetime | None = None) -> str:
    return (now or datetime.now()).strftime("%Y-%m-%d %H:%M")


def parse(text: str) -> dict[str, str]:
    """Return ``{key: value}`` for every ``key: value`` line; headings and blanks are skipped."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip()
    return out


def validate(text: str) -> str | None:
    """Return an error message when ``text`` breaks the MOOD.md contract, else ``None``."""
    fields = parse(text)
    missing = [k for k in REQUIRED_KEYS if k not in fields]
    if missing:
        return f"missing keys: {', '.join(missing)}"
    if fields["mood"] not in MOODS:
        return f"bad mood value: {fields['mood']!r}"
    if fields["warmth"] not in WARMTHS:
        return f"bad warmth value: {fields['warmth']!r}"
    if fields["warmth_trend"] not in TRENDS:
        return f"bad warmth_trend value: {fields['warmth_trend']!r}"
    too_long = [k for k, v in fields.items() if len(v) > MAX_VALUE_LEN]
    if too_long:
        return f"values too long: {', '.join(too_long)}"
    if "```" in text:
        return "code fence in output"
    return None


def strip_fences(text: str) -> str:
    """Models sometimes wrap the file in ``` fences despite instructions; unwrap them."""
    t = text.strip()
    if t.startswith("```"):
        first_nl = t.find("\n")
        t = t[first_nl + 1:] if first_nl != -1 else ""
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip() + "\n"


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".mood-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def ensure_file(path: Path) -> None:
    """Create MOOD.md from the template when missing. Never overwrites an existing file."""
    if path.exists():
        return
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    template = template.replace("mood_since:", f"mood_since: {now_label()}", 1)
    template = template.replace("last_update:", f"last_update: {now_label()}", 1)
    write_atomic(path, template)


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def soul_excerpt(limit: int = 2000) -> str:
    """First ``limit`` chars of $HERMES_HOME/SOUL.md, or a placeholder. Read-only, always."""
    try:
        text = (hermes_home() / "SOUL.md").read_text(encoding="utf-8").strip()
    except OSError:
        return "(no SOUL.md found)"
    return text[:limit] if text else "(SOUL.md is empty)"
