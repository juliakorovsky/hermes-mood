import importlib.util
import sys
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[1]
PKG = "hermes_mood"


def _load_package():
    if PKG in sys.modules:
        return sys.modules[PKG]
    spec = importlib.util.spec_from_file_location(
        PKG, PLUGIN_DIR / "__init__.py", submodule_search_locations=[str(PLUGIN_DIR)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[PKG] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def plugin():
    return _load_package()


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / "SOUL.md").write_text("You are Jarvis. Sardonic, loyal.", encoding="utf-8")
    return tmp_path


class FakeLlm:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def complete(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.reply, Exception):
            raise self.reply

        class R:
            text = self.reply

        return R()


class FakeCtx:
    def __init__(self, reply="", settings=None):
        self.llm = FakeLlm(reply)
        self.hooks = {}
        self.aux = []
        self.settings = settings or {}

    def get_config(self, key, default=None):
        return self.settings.get(key, default)

    def register_hook(self, name, cb):
        self.hooks[name] = cb

    def register_auxiliary_task(self, key, **kw):
        self.aux.append((key, kw))


@pytest.fixture
def fake_ctx():
    return FakeCtx


class FakeJobs:
    def __init__(self, jobs=None):
        self.jobs = list(jobs or [])
        self.created = []
        self.updated = []
        self.removed = []

    def list_jobs(self, include_disabled=False):
        return list(self.jobs)

    def create_job(self, prompt, schedule, **kw):
        job = {"id": "abc123", "name": kw.get("name"), "prompt": prompt, "schedule": schedule, **kw}
        self.jobs.append(job)
        self.created.append(job)
        return job

    def update_job(self, job_id, updates):
        self.updated.append((job_id, updates))
        for j in self.jobs:
            if j["id"] == job_id:
                j.update(updates)
                return j
        return None

    def remove_job(self, job_id):
        before = len(self.jobs)
        self.jobs = [j for j in self.jobs if j["id"] != job_id]
        self.removed.append(job_id)
        return len(self.jobs) != before


@pytest.fixture
def fake_jobs():
    return FakeJobs
