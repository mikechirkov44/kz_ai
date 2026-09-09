from types import SimpleNamespace

from app.domain.mail import parse_recipients
from app.services.email_digest import check_smtp_connection, send_weekly_digest
from app.services.mail_settings import MailConfig, settings_public_view


def test_parse_recipients():
    assert parse_recipients("a@b.ru, c@d.ru") == ["a@b.ru", "c@d.ru"]
    assert parse_recipients("a@b.ru; a@b.ru\n x@y.kz") == ["a@b.ru", "x@y.kz"]
    assert parse_recipients("") == []
    assert parse_recipients("not-an-email") == []


def test_mail_public_view_hides_password():
    row = SimpleNamespace(
        enabled=True,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="user",
        smtp_password_encrypted="cipher",
        smtp_from="from@example.com",
        use_tls=True,
        recipients="to@example.com",
        include_quarterly=True,
        include_behind=False,
        include_recommendations=True,
        updated_at=None,
    )
    view = settings_public_view(row)
    assert view["password_set"] is True
    assert "cipher" not in view.values()
    assert "smtp_password" not in view


def test_check_smtp_missing_host():
    config = MailConfig(
        enabled=True,
        smtp_host="",
        smtp_port=587,
        smtp_user="",
        smtp_password="",
        smtp_from="",
        use_tls=True,
        recipients=[],
        include_quarterly=True,
        include_behind=True,
        include_recommendations=False,
    )
    assert check_smtp_connection(config)["status"] == "error"


class _FakeSmtp:
    def __init__(self, *args, **kwargs):
        self.started = False
        self.logged = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self):
        self.started = True

    def login(self, user, password):
        self.logged = True
        assert user == "u"
        assert password == "p"


def test_check_smtp_ok():
    config = MailConfig(
        enabled=True,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="u",
        smtp_password="p",
        smtp_from="from@example.com",
        use_tls=True,
        recipients=["to@example.com"],
        include_quarterly=True,
        include_behind=True,
        include_recommendations=False,
    )
    result = check_smtp_connection(config, smtp_cls=_FakeSmtp)
    assert result["status"] == "ok"


class _CaptureSmtp(_FakeSmtp):
    last_message = None

    def send_message(self, msg):
        type(self).last_message = msg


def _mail_config(**overrides) -> MailConfig:
    data = dict(
        enabled=True,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="u",
        smtp_password="p",
        smtp_from="from@example.com",
        use_tls=True,
        recipients=["to@example.com"],
        include_quarterly=True,
        include_behind=True,
        include_recommendations=False,
    )
    data.update(overrides)
    return MailConfig(**data)


def test_send_weekly_digest_html_and_xlsx(monkeypatch):
    from app.services import email_digest as digest

    progress = SimpleNamespace(
        clients=[
            SimpleNamespace(
                counterparty="ИП A",
                manager_name="Иванов",
                work_type_label="Рост",
                work_type="growth",
                work_type_percent=10,
                plan=100,
                fact=40,
                percent=40,
                dynamics=0.8,
            )
        ],
        slices=[SimpleNamespace(name="Всего", clients=1, fulfilled=0, percent=40)],
    )
    results = {
        "labels": {"plan": "План отгрузок на 3 квартал"},
        "clients": [{"counterparty": "ИП A", "plan": 100, "shipment_fact": 40, "shipment_percent": 40}],
    }
    monkeypatch.setattr(digest, "get_mail_config", lambda _db: _mail_config())
    monkeypatch.setattr(digest, "build_quarterly_plans_report", lambda *_a, **_k: progress)
    monkeypatch.setattr(digest, "build_quarterly_results", lambda *_a, **_k: results)

    _CaptureSmtp.last_message = None
    result = send_weekly_digest(None, year=2026, quarter=3, force_send=True, smtp_cls=_CaptureSmtp)
    assert result["sent"] is True
    assert result["attachments"] == ["quarterly_progress_2026_Q3.xlsx", "quarterly_results_2026_Q3.xlsx"]
    msg = _CaptureSmtp.last_message
    assert msg is not None
    html_body = msg.get_body(preferencelist=("html",)).get_content()
    assert "text/html" in msg.as_string()
    assert "Промежуточные итоги 2026 Q3" in html_body
    assert "Итоги квартала 2026 Q3" in html_body
    names = [part.get_filename() for part in msg.iter_attachments()]
    assert names == ["quarterly_progress_2026_Q3.xlsx", "quarterly_results_2026_Q3.xlsx"]
