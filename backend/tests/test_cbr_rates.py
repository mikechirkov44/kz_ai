from datetime import date
from decimal import Decimal

from app.services.cbr_rates import (
    build_cbr_rates,
    change_percent,
    parse_cbr_date,
    parse_cbr_decimal,
    parse_daily_xml,
    parse_dynamic_xml,
)

DAILY_XML = """<?xml version="1.0" encoding="windows-1251"?>
<ValCurs Date="04.09.2026" name="Foreign Currency Market">
    <Valute ID="R01235">
        <NumCode>840</NumCode>
        <CharCode>USD</CharCode>
        <Nominal>1</Nominal>
        <Name>Доллар США</Name>
        <Value>86,8900</Value>
        <VunitRate>86.89</VunitRate>
    </Valute>
    <Valute ID="R01239">
        <NumCode>978</NumCode>
        <CharCode>EUR</CharCode>
        <Nominal>1</Nominal>
        <Name>Евро</Name>
        <Value>100,6000</Value>
        <VunitRate>100.6</VunitRate>
    </Valute>
    <Valute ID="R01335">
        <NumCode>398</NumCode>
        <CharCode>KZT</CharCode>
        <Nominal>100</Nominal>
        <Name>Тенге</Name>
        <Value>18,5200</Value>
        <VunitRate>0.1852</VunitRate>
    </Valute>
</ValCurs>
"""

USD_HISTORY = """<?xml version="1.0" encoding="windows-1251"?>
<ValCurs ID="R01235" DateRange1="01.09.2026" DateRange2="04.09.2026" name="Foreign Currency Market">
    <Record Date="02.09.2026" Id="R01235">
        <Nominal>1</Nominal>
        <Value>87,0000</Value>
        <VunitRate>87</VunitRate>
    </Record>
    <Record Date="03.09.2026" Id="R01235">
        <Nominal>1</Nominal>
        <Value>87,0031</Value>
        <VunitRate>87.0031</VunitRate>
    </Record>
</ValCurs>
"""

KZT_HISTORY = """<?xml version="1.0" encoding="windows-1251"?>
<ValCurs ID="R01335" DateRange1="01.09.2026" DateRange2="04.09.2026">
    <Record Date="03.09.2026" Id="R01335">
        <Nominal>100</Nominal>
        <Value>18,5000</Value>
        <VunitRate>0.185</VunitRate>
    </Record>
</ValCurs>
"""


def test_parse_cbr_decimal_and_date():
    assert parse_cbr_decimal("86,89") == Decimal("86.89")
    assert parse_cbr_date("04.09.2026") == date(2026, 9, 4)
    assert parse_cbr_date("04/09/2026") == date(2026, 9, 4)


def test_parse_daily_uses_unit_rate():
    as_of, by_code = parse_daily_xml(DAILY_XML)
    assert as_of == date(2026, 9, 4)
    assert by_code["USD"]["rate"] == Decimal("86.89")
    assert by_code["KZT"]["rate"] == Decimal("0.1852")
    assert by_code["KZT"]["nominal"] == Decimal("100")


def test_parse_dynamic_and_change():
    rows = parse_dynamic_xml(USD_HISTORY)
    assert len(rows) == 2
    assert rows[0][1] == Decimal("87")
    assert change_percent(Decimal("99.87"), Decimal("100")) == Decimal("-0.13")
    assert change_percent(Decimal("100.23"), Decimal("100")) == Decimal("0.23")


def test_build_cbr_rates_per_unit():
    payload = build_cbr_rates(
        DAILY_XML,
        {"USD": USD_HISTORY, "EUR": "", "KZT": KZT_HISTORY},
    )
    by_code = {item["code"]: item for item in payload["items"]}
    assert payload["status"] == "ok"
    assert by_code["USD"]["rate"] == Decimal("86.89")
    assert by_code["USD"]["change_percent"] == change_percent(Decimal("86.89"), Decimal("87.0031"))
    assert by_code["KZT"]["rate"] == Decimal("0.1852")
    assert by_code["KZT"]["history"][-1]["rate"] == Decimal("0.1852")
    assert len(by_code["EUR"]["history"]) == 1
