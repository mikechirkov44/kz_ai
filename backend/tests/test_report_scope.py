from uuid import uuid4

from app.services.scope import intersect_allowed


def test_intersect_allowed_keeps_only_the_chosen_base():
    asil = uuid4()
    other = uuid4()
    assert intersect_allowed(None, {asil}) == {asil}
    assert intersect_allowed({asil, other}, {asil}) == {asil}
    assert intersect_allowed({other}, {asil}) == set()
