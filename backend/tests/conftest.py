"""Keep test requests out of the real log: every test writes to its own tmp JSONL."""
import pytest


@pytest.fixture(autouse=True)
def _obs_log_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("OBS_LOG_PATH", str(tmp_path / "requests.jsonl"))
