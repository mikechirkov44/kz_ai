from app.workers import tasks


class _DummySession:
    def close(self) -> None:
        return None


def test_tick_skips_when_schedule_is_not_due(monkeypatch):
    monkeypatch.setattr(tasks, "SessionLocal", lambda: _DummySession())
    monkeypatch.setattr(tasks, "due_incremental", lambda db: False)
    assert tasks.tick_scheduled_sync() == {"skipped": True, "reason": "not due"}


def test_tick_runs_incremental_when_due(monkeypatch):
    dispatched: list[object] = []
    monkeypatch.setattr(tasks, "SessionLocal", lambda: _DummySession())
    monkeypatch.setattr(tasks, "due_incremental", lambda db: True)
    monkeypatch.setattr(tasks, "mark_dispatched", lambda db: dispatched.append(db))
    monkeypatch.setattr(tasks, "sync_all_enabled", lambda db, **kwargs: {"ok": True, "full": kwargs.get("full")})
    assert tasks.tick_scheduled_sync() == {"ok": True, "full": False}
    assert len(dispatched) == 1


def test_manual_run_sync_queues_selected_items(monkeypatch):
    monkeypatch.setattr(tasks, "SessionLocal", lambda: _DummySession())
    monkeypatch.setattr(
        tasks,
        "sync_all_enabled",
        lambda db, **kwargs: {"ok": True, "items": kwargs.get("items")},
    )
    result = tasks._run_sync(full=True, items=[{"source_id": "asil", "entity": "realization"}])
    assert result["ok"] is True
    assert result["items"] == [("asil", "realization")]
