from app.workers import tasks


class _DummySession:
    def close(self) -> None:
        return None


def test_tick_skips_when_sync_disabled(monkeypatch):
    monkeypatch.setattr(tasks.settings, "sync_enabled", False)
    assert tasks.tick_scheduled_sync() == {"skipped": True, "reason": "SYNC_ENABLED=false"}


def test_manual_run_sync_ignores_env_flag(monkeypatch):
    monkeypatch.setattr(tasks.settings, "sync_enabled", False)
    monkeypatch.setattr(tasks, "SessionLocal", _DummySession)
    monkeypatch.setattr(
        tasks,
        "sync_all_enabled",
        lambda db, **kwargs: {"ok": True, "items": kwargs.get("items")},
    )
    result = tasks._run_sync(full=True, items=[{"source_id": "asil", "entity": "realization"}])
    assert result["ok"] is True
    assert result["items"] == [("asil", "realization")]
