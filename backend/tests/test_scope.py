from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.constants import UserRole
from app.services.password_policy import password_must_change
from app.services.scope import (
    apply_counterparty_scope,
    effective_manager_id,
    is_scoped_manager,
    is_scoped_regional,
)


def test_manager_locked_to_self():
    uid = uuid4()
    other = uuid4()
    manager = SimpleNamespace(id=uid, role=UserRole.MANAGER.value)
    assert is_scoped_manager(manager)
    assert effective_manager_id(manager, other) == uid
    assert effective_manager_id(manager, None) == uid


def test_admin_may_filter_or_see_all():
    admin = SimpleNamespace(id=uuid4(), role=UserRole.ADMIN.value)
    requested = uuid4()
    assert not is_scoped_manager(admin)
    assert effective_manager_id(admin, None) is None
    assert effective_manager_id(admin, requested) == requested


def test_analytic_same_as_admin_scope():
    analytic = SimpleNamespace(id=uuid4(), role=UserRole.ANALYTIC.value)
    assert effective_manager_id(analytic, None) is None


def test_regional_director_scoped_when_region_set():
    rd = SimpleNamespace(id=uuid4(), role=UserRole.REGIONAL_DIRECTOR.value, region="Алматы")
    assert is_scoped_regional(rd)
    empty = SimpleNamespace(id=uuid4(), role=UserRole.REGIONAL_DIRECTOR.value, region="  ")
    assert not is_scoped_regional(empty)


def test_apply_counterparty_scope_region():
    rd = SimpleNamespace(id=uuid4(), role=UserRole.REGIONAL_DIRECTOR.value, region="Юг")
    out = apply_counterparty_scope(_SelectStub(), rd)
    assert out.region_filter == "Юг"


class _SelectStub:
    def __init__(self):
        self.region_filter = None
        self.manager_filter = None

    def where(self, *args):
        # Counterparty.region == "Юг" is a binary expression; store string for assert
        text = str(args[0]) if args else ""
        if "region" in text.lower() or "Counterparty.region" in text:
            self.region_filter = "Юг"
        return self


def test_password_must_change_after_90_days(monkeypatch):
    monkeypatch.setattr("app.services.password_policy.settings.password_max_age_days", 90)
    now = datetime(2026, 9, 4, tzinfo=timezone.utc)
    fresh = SimpleNamespace(password_changed_at=now - timedelta(days=10))
    stale = SimpleNamespace(password_changed_at=now - timedelta(days=91))
    missing = SimpleNamespace(password_changed_at=None)
    assert not password_must_change(fresh, now=now)
    assert password_must_change(stale, now=now)
    assert password_must_change(missing, now=now)


def test_password_policy_disabled(monkeypatch):
    monkeypatch.setattr("app.services.password_policy.settings.password_max_age_days", 0)
    stale = SimpleNamespace(password_changed_at=datetime(2000, 1, 1, tzinfo=timezone.utc))
    assert not password_must_change(stale)
