import jwt

from app.auth.security import create_access_token, decode_access_token, hash_password, verify_password


def test_hash_and_verify_password():
    hashed = hash_password("Passw0rd!")
    assert hashed != "Passw0rd!"
    assert verify_password("Passw0rd!", hashed)
    assert not verify_password("wrong", hashed)


def test_hash_verifies_wrong_hash_returns_false():
    assert verify_password("Passw0rd!", "not-a-bcrypt-hash") is False


def test_jwt_roundtrip():
    token = create_access_token({"userid": "LD1", "role": "user"})
    payload = decode_access_token(token)
    assert payload["userid"] == "LD1"
    assert payload["role"] == "user"
    assert "exp" in payload


def test_jwt_invalid_token():
    try:
        decode_access_token("garbage.token.here")
    except jwt.InvalidTokenError:
        assert True
    else:
        raise AssertionError("expected InvalidTokenError")
