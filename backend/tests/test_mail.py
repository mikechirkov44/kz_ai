from types import SimpleNamespace

from app.domain.mail import parse_recipients
from app.services.email_digest import check_smtp_connection
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
