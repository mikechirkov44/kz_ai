from types import SimpleNamespace
from uuid import uuid4

from app.constants import UserRole
from app.services.scope import effective_manager_id, is_scoped_manager


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
