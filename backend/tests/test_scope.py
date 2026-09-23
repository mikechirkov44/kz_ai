from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.constants import UserRole
from app.domain.managers import (
    counterparty_belongs_to_manager,
    display_manager_name,
    normalize_manager_name,
)
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


def test_apply_counterparty_scope_uses_resolved_ids():
    class FakeDb:
        def get(self, model, mid):
            return SimpleNamespace(id=mid, full_name="Иванов", manager_id=None)

        def scalars(self, stmt):
            return SimpleNamespace(all=lambda: [])

    rd = SimpleNamespace(id=uuid4(), role=UserRole.REGIONAL_DIRECTOR.value, region="Юг")

    class Stub:
        def __init__(self):
            self.filtered = False

        def where(self, *args):
            self.filtered = True
            return self

    # Regional with empty DB → empty allowed set → false() filter applied
    out = apply_counterparty_scope(Stub(), FakeDb(), rd)
    assert out.filtered is True


def test_display_and_belong_use_onec_name():
    user = SimpleNamespace(id=uuid4(), full_name="Гончарова Алена")
    cp = SimpleNamespace(
        manager_id=None,
        onec_manager_name="Гончарова  Алена",
        extra_properties=None,
    )
    assert normalize_manager_name("Гончарова  Алена") == "гончарова алена"
    assert display_manager_name(cp) == "Гончарова  Алена"
    assert counterparty_belongs_to_manager(cp, user)
    other = SimpleNamespace(id=uuid4(), full_name="Петров")
    assert not counterparty_belongs_to_manager(cp, other)


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
