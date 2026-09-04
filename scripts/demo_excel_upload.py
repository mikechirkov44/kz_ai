"""Generate sample Excel files and upload them to a running API.

Usage (from repo root, API on :8000):
  python scripts/demo_excel_upload.py
"""
from __future__ import annotations

import io
import os
import sys
from datetime import date
from pathlib import Path

import httpx
import pandas as pd

API = os.getenv("API_URL", "http://localhost:8000")
EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
PASSWORD = os.getenv("ADMIN_PASSWORD", "admin12345")
OUT = Path(__file__).resolve().parents[1] / "uploads" / "samples"


def _cp_name(name: str) -> str:
    return " ".join(str(name).split())


def _xlsx(columns: list[str], rows: list[list]) -> bytes:
    buf = io.BytesIO()
    pd.DataFrame(rows, columns=columns).to_excel(buf, index=False)
    return buf.getvalue()


def _post_file(client: httpx.Client, path: str, filename: str, content: bytes, fields: dict[str, str]) -> dict:
    files = {"file": (filename, content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    res = client.post(f"{API}{path}", files=files, data=fields, timeout=60.0)
    print(path, filename, res.status_code, res.text[:500])
    res.raise_for_status()
    return res.json()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with httpx.Client() as client:
        login = client.post(
            f"{API}/api/v1/auth/login",
            json={"email": EMAIL, "password": PASSWORD},
            timeout=30.0,
        )
        print("LOGIN", login.status_code)
        if login.status_code != 200:
            print(login.text[:400])
            return 1
        token = login.json()["access_token"]
        client.headers["Authorization"] = f"Bearer {token}"

        cps = client.get(f"{API}/api/v1/counterparties", timeout=30.0).json()
        noms = client.get(f"{API}/api/v1/catalogs/nomenclature?page_size=50", timeout=30.0).json()
        items = noms.get("items") if isinstance(noms, dict) else []
        article = next((n.get("article") for n in items if n.get("article")), "IM-001")
        cp = next((c for c in cps if not c.get("is_folder")), None)
        name = _cp_name(cp["name"]) if cp else "ТОО Пример Excel"
        shops = cp.get("shops") or [] if cp else []
        shop = shops[0] if shops else ""
        lettered = next((n.get("article") for n in items if n.get("article") and any(ch.isalpha() for ch in str(n["article"]))), None)
        article = lettered or next((n.get("article") for n in items if n.get("article")), "IM-001")

        sales_cols = ["Головной контрагент", "Артикул", "Магазин", "Количество", "Цена продажи"]
        stock_cols = ["Головной контрагент", "Артикул", "Магазин", "Количество"]
        good_sales = _xlsx(sales_cols, [[name, article, shop, 2, 95000]])
        good_stocks = _xlsx(stock_cols, [[name, article, shop, 5]])
        good_promo = _xlsx(stock_cols, [[name, article, shop, 1]])
        bad_sales = _xlsx(
            sales_cols,
            [
                [name, article, shop, 1, 10000],
                ["Несуществующий контрагент", "BAD-ART", "X", -3, "нет"],
            ],
        )

        (OUT / "sample_sales.xlsx").write_bytes(good_sales)
        (OUT / "sample_stocks.xlsx").write_bytes(good_stocks)
        (OUT / "sample_promo.xlsx").write_bytes(good_promo)
        (OUT / "sample_sales_errors.xlsx").write_bytes(bad_sales)
        print("Wrote", OUT)

        today = date.today()
        sales = _post_file(
            client,
            "/api/v1/uploads/sales",
            "sample_sales.xlsx",
            good_sales,
            {"period_year": str(today.year), "period_month": str(today.month), "upload_type": "sales"},
        )
        stocks = _post_file(
            client,
            "/api/v1/uploads/sales",
            "sample_stocks.xlsx",
            good_stocks,
            {
                "period_year": str(today.year),
                "period_month": str(today.month),
                "upload_type": "stocks",
                "stock_date": today.isoformat(),
            },
        )
        promo = _post_file(
            client,
            "/api/v1/uploads/promo-motivation",
            "sample_promo.xlsx",
            good_promo,
            {"stock_date": today.isoformat()},
        )
        bad = _post_file(
            client,
            "/api/v1/uploads/sales",
            "sample_sales_errors.xlsx",
            bad_sales,
            {"period_year": str(today.year), "period_month": str(today.month), "upload_type": "sales"},
        )
        print("RESULT sales", sales)
        print("RESULT stocks", stocks)
        print("RESULT promo", promo)
        print("RESULT bad", bad)
        if bad.get("upload_id") and bad.get("errors"):
            err = client.get(f"{API}/api/v1/uploads/{bad['upload_id']}/errors.xlsx", timeout=30.0)
            print("errors.xlsx", err.status_code, "bytes", len(err.content), "pk=", err.content[:2] == b"PK")
            (OUT / "errors_download.xlsx").write_bytes(err.content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
