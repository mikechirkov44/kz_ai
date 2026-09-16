from decimal import Decimal
from uuid import uuid4

from app.services.counterparty_utils import counterparty_trees
from app.services.reports import (
    batch_avg_realization_prices,
    resolve_motivation_ids,
    rollup_avg_realization_prices,
    weighted_unit_price,
)


def test_counterparty_trees_groups_shops():
    head, shop, other = uuid4(), uuid4(), uuid4()

    class Fake:
        def execute(self, _stmt):
            return [(shop, head), (other, uuid4())]

    trees = counterparty_trees(Fake(), [head])
    assert trees[head] == {head, shop}


def test_rollup_sums_and_averages_include_shops():
    from app.services.counterparty_utils import (
        group_rows_by_head,
        rollup_averages_to_head,
        rollup_sums_to_head,
    )

    head, shop = uuid4(), uuid4()
    to_head = {head: head, shop: head}
    assert rollup_sums_to_head(
        [(head, Decimal("2")), (shop, Decimal("3")), (None, Decimal("9"))],
        to_head,
    ) == {head: Decimal("5")}
    avgs = rollup_averages_to_head(
        [
            (head, "Кольцо", Decimal("100"), 1),
            (shop, "Кольцо", Decimal("300"), 3),
            (shop, "Серьги", Decimal("50"), 1),
        ],
        to_head,
    )
    assert avgs[head]["Кольцо"] == Decimal("100")
    assert avgs[head]["Серьги"] == Decimal("50")
    grouped = group_rows_by_head(
        [type("Row", (), {"counterparty_id": shop})(), type("Row", (), {"counterparty_id": head})()],
        to_head,
        counterparty_id_of=lambda row: row.counterparty_id,
    )
    assert len(grouped[head]) == 2


def test_counterparty_trees_empty():
    class Boom:
        def execute(self, _stmt):
            raise AssertionError("no query")

    assert counterparty_trees(Boom(), []) == {}


def test_rollup_avg_sums_head_and_shops():
    head, shop, nom = uuid4(), uuid4(), uuid4()
    result = rollup_avg_realization_prices(
        [(head, "A1")],
        trees={head: {head, shop}},
        article_nom={"A1": nom},
        sums={
            (head, nom): (Decimal("100000"), Decimal("1")),
            (shop, nom): (Decimal("300000"), Decimal("3")),
        },
    )
    assert result[(head, "A1")] == weighted_unit_price(Decimal("400000"), Decimal("4"))
    assert result[(head, "A1")] == Decimal("100000")


def test_rollup_avg_missing_nomenclature():
    head = uuid4()
    result = rollup_avg_realization_prices(
        [(head, "A1")],
        trees={head: {head}},
        article_nom={"A1": None},
        sums={},
    )
    assert result[(head, "A1")] is None


def test_batch_avg_skips_empty_pairs():
    class Boom:
        def execute(self, *_args, **_kwargs):
            raise AssertionError("no query")

    assert batch_avg_realization_prices(Boom(), [], {}) == {}


def test_resolve_motivation_ids_merges_legacy_and_list():
    first, second = uuid4(), uuid4()
    assert resolve_motivation_ids(None, None) == []
    assert resolve_motivation_ids(first, None) == [first]
    assert resolve_motivation_ids(first, [second, first]) == [second, first]
    assert resolve_motivation_ids(None, [first, first, second]) == [first, second]
