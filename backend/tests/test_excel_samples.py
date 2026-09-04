from pathlib import Path

import pandas as pd

from app.domain.excel_validation import map_headers, validate_upload_dataframe


def _write(path: Path, columns: list[str], rows: list[list]) -> None:
    df = pd.DataFrame(rows, columns=columns)
    df.to_excel(path, index=False)


def test_stored_upload_path():
    from app.config import settings
    from app.services.uploads import stored_upload_path

    path = stored_upload_path("abc123", "sales.xlsx")
    assert path.name == "abc123_sales.xlsx"
    assert path.parent == Path(settings.upload_dir)


def test_generated_sales_file_validates(tmp_path: Path):
    path = tmp_path / "sales.xlsx"
    _write(
        path,
        ["Головной контрагент", "Артикул", "Магазин", "Количество", "Цена продажи"],
        [["ТОО Demo", "IM-001", "ЦУМ", 2, 95000]],
    )
    records = pd.read_excel(path).to_dict(orient="records")
    result = validate_upload_dataframe(
        records,
        known_counterparties={"ТОО Demo": "1"},
        known_articles={"IM-001"},
        counterparty_shops={"ТОО Demo": {"ЦУМ"}},
        require_price=False,
    )
    assert result.status == "success"
    assert len(result.rows) == 1
    assert result.rows[0].quantity == 2


def test_leading_space_counterparty_and_numeric_article():
    from app.domain.articles import article_lookup_keys, build_known_articles
    from app.domain.excel_validation import normalize_counterparty_name
    from types import SimpleNamespace

    assert normalize_counterparty_name(" ИП Saona") == "ИП Saona"
    assert "1797" in article_lookup_keys("000001797")
    noms = [SimpleNamespace(article="000001797", barcode=None)]
    assert "1797" in build_known_articles(noms)

    result = validate_upload_dataframe(
        [{"Головной контрагент": " ИП Saona", "Артикул": 1797, "Магазин": "", "Количество": 1}],
        known_counterparties={"ИП Saona": "1"},
        known_articles=build_known_articles(noms),
        counterparty_shops={"ИП Saona": set()},
    )
    assert result.status == "success"


def test_generated_error_file_collects_all(tmp_path: Path):
    path = tmp_path / "bad.xlsx"
    _write(
        path,
        ["Головной контрагент", "Артикул", "Магазин", "Количество", "Цена продажи"],
        [
            ["ТОО Demo", "IM-001", "ЦУМ", 1, 10000],
            ["Другой", "NOPE", "X", -1, "abc"],
        ],
    )
    records = pd.read_excel(path).to_dict(orient="records")
    result = validate_upload_dataframe(
        records,
        known_counterparties={"ТОО Demo": "1"},
        known_articles={"IM-001"},
        counterparty_shops={"ТОО Demo": {"ЦУМ"}},
    )
    assert result.status == "error"
    fields = {e.field for e in result.errors}
    assert "head_counterparty" in fields
    assert "article" in fields
    assert "quantity" in fields


def test_template_header_mapping():
    for headers in (
        ["Головной контрагент", "Артикул", "Магазин", "Количество", "Цена продажи"],
        ["Головной контрагент", "Артикул", "Магазин", "Количество"],
    ):
        mapped = map_headers(headers)
        assert {"head", "article", "qty"} <= mapped.keys()
