from app.security import decrypt_secret, encrypt_secret


def test_encrypt_decrypt_roundtrip():
    token = encrypt_secret("odata-password")
    assert token != "odata-password"
    assert decrypt_secret(token) == "odata-password"


def test_decrypt_plain_legacy():
    assert decrypt_secret("plain-value") == "plain-value"
