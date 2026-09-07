# hermes-mood

Mood, grudges and relationship warmth for a [Hermes Agent](https://github.com/NousResearch/hermes-agent).

Your agent gets a small text file that says how it feels, whether it is holding a grudge, and how warm things are between you two. The file is injected into every turn, so the persona in your `SOUL.md` has something to act on. It is rewritten by a cheap model after each pause in conversation, not on a timer. In idle hours the agent reads the file and its own notes and may write to you first, or stays silent.

What it deliberately does not do:

- It never edits `SOUL.md`, memory, or anything but its own two files.
- A grudge does not fade from thanks, praise, or good work. Only talking it through or an apology clears it.
- No numbers. The state is words the model actually understands.

## The file

`~/.hermes/MOOD.md`:

```
# Mood and relationship

mood: irritated
mood_since: 2026-09-07 14:05
mood_reason: browser crashed three times and she blamed me

grudge: none
grudge_since:

warmth: even
warmth_trend: cooling
warmth_reason: the afternoon was commands only

last_conflict: 2026-09-07 14:03 browser crash argument
last_good_moment: 2026-09-06 evening, she laughed at the fruit joke
last_update: 2026-09-07 14:05
```

`mood` is one of calm / content / curious / tired / irritated / hurt / withdrawn. `warmth` is warm / even / cool / cold and moves at most one step per update. Rules are in `prompts/update.md`; edit them there.

## How it works

1. `post_llm_call` buffers every exchange. Each new message restarts a timer (default 3 minutes).
2. When you go quiet, the whole batch, the current file and an excerpt of `SOUL.md` go to the model in one call. Batches made only of short commands ("ok", "run it again") are skipped without a call.
3. The model returns the whole file. If it breaks the format, the file is left unchanged.
4. `pre_llm_call` prepends a short note (`prompts/persona.md`) and the file to your next message.
5. On start the plugin creates one cron job, `mood-idle-reflection`, that runs the agent in idle hours with `prompts/idle.md`. It answers `SILENT` unless there is something worth saying.

## Install

```bash
git clone https://github.com/<you>/hermes-mood ~/.hermes/plugins/hermes-mood
hermes plugins enable hermes-mood
systemctl --user restart hermes-gateway   # or: hermes gateway restart
```

Requirements: a working provider for the main model, `SOUL.md` with an actual persona, and a home channel for delivery (Telegram by default) if you want idle messages.

## Settings

All under `plugins.entries.hermes-mood.settings` in `~/.hermes/config.yaml`, or as environment variables with the `HERMES_MOOD_` prefix (env wins).

| Key | Default | Meaning |
|---|---|---|
| `pause_seconds` | `180` | Quiet time after your last message before the file is rewritten |
| `min_words` | `6` | Messages shorter than this with no emotional content count as trivial |
| `update_enabled` | `true` | Turn the rewrite off entirely |
| `update_provider` / `update_model` | `openrouter` / `anthropic/claude-haiku-4.5` | Cheap model for the rewrite (registered as auxiliary task `hermes_mood_update`, so `auxiliary.hermes_mood_update` in config also works) |
| `idle_enabled` | `true` | Create the idle-reflection cron job; `false` removes it |
| `idle_schedule` | `0 10,14,18,22 * * *` | Cron expression, in your Hermes timezone |
| `idle_deliver` | `telegram` | Any Hermes cron delivery target |
| `idle_provider` / `idle_model` | your main model | Pin for the idle job, so it speaks in the agent's own voice |
| `mood_file` / `reflections_file` | `MOOD.md` / `reflections.md` | Relative to `HERMES_HOME`, or absolute |

## Tests

```bash
pip install pytest
pytest tests -q
```

Tests mock Hermes entirely; no install needed.

## License

MIT
